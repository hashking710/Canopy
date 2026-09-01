from sqlalchemy import select
from sqlalchemy.orm import Session

from canopy_agent.compliance_models import Harvest, LabTest, Package, Strain


def _potency_for_package(db: Session, package_id: str) -> tuple[float | None, float | None]:
    """Prefers this package's own most recent passed potency test — the actual,
    tested truth for this specific lot — over anything a linked Strain merely
    claims is "typical". Falls back to (None, None) if there's no lab test at all;
    the caller falls back further to the strain's typical values, if any."""
    test = db.execute(
        select(LabTest)
        .where(LabTest.package_id == package_id, LabTest.test_type == "potency", LabTest.result == "pass")
        .order_by(LabTest.tested_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if test is None:
        return None, None
    return test.thc_pct, test.cbd_pct


def build_menu_items(db: Session) -> list[dict]:
    """
    Assembles the current sellable-inventory snapshot for menu_sync plugins (see
    menu_sync/base.py) to push out — one item per active Package, enriched with
    genetics (from a linked Strain, if any, else just the harvest's free-text
    strain name) and potency (this package's own lab test, falling back to the
    strain's typical values, falling back to None). Intentionally doesn't touch
    packages that aren't `status == "active"` — sold/destroyed/transferred/processed
    inventory has nothing to list.
    """
    packages = db.execute(select(Package).where(Package.status == "active")).scalars().all()

    items: list[dict] = []
    for package in packages:
        harvest = db.get(Harvest, package.harvest_id) if package.harvest_id else None
        strain = db.get(Strain, harvest.strain_id) if harvest and harvest.strain_id else None

        thc_pct, cbd_pct = _potency_for_package(db, package.id)
        if thc_pct is None and cbd_pct is None and strain is not None:
            thc_pct, cbd_pct = strain.thc_pct_typical, strain.cbd_pct_typical

        items.append(
            {
                "package_id": package.id,
                "item_name": package.item_name,
                "weight_g": package.weight_g,
                "price_cents": package.list_price_cents,
                "room_id": package.room_id,
                "strain_name": strain.name if strain else (harvest.strain if harvest else None),
                "strain_type": strain.strain_type if strain else None,
                "lineage": strain.lineage if strain else None,
                "thc_pct": thc_pct,
                "cbd_pct": cbd_pct,
            }
        )
    return items
