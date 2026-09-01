from datetime import date

from canopy_agent.compliance_models import Harvest, LabTest, Package, Strain
from canopy_agent.services.menu_data import build_menu_items


def make_harvest(db_session, harvest_id="harvest-1", strain="GMO", strain_id=None):
    harvest = Harvest(
        id=harvest_id, name=harvest_id, strain=strain, strain_id=strain_id,
        source_room_id="room-1", wet_weight_g=1000.0,
    )
    db_session.add(harvest)
    db_session.commit()
    return harvest


def make_package(db_session, package_id="pkg-1", harvest_id="harvest-1", price_cents=None):
    package = Package(
        id=package_id, harvest_id=harvest_id, item_name="Flower", weight_g=453.6,
        room_id="room-1", list_price_cents=price_cents,
    )
    db_session.add(package)
    db_session.commit()
    return package


def make_lab_test(db_session, package_id, thc_pct, cbd_pct, tested_at, result="pass"):
    test = LabTest(
        id=f"test-{package_id}-{tested_at.isoformat()}", package_id=package_id, lab_name="Test Lab",
        test_type="potency", result=result, thc_pct=thc_pct, cbd_pct=cbd_pct, tested_at=tested_at,
    )
    db_session.add(test)
    db_session.commit()
    return test


def test_active_package_with_no_harvest_link_has_no_strain_info(db_session):
    make_package(db_session, harvest_id=None)
    items = build_menu_items(db_session)
    assert items[0]["strain_name"] is None
    assert items[0]["thc_pct"] is None


def test_falls_back_to_harvest_free_text_strain_when_unlinked(db_session):
    make_harvest(db_session, strain="GMO", strain_id=None)
    make_package(db_session)
    items = build_menu_items(db_session)
    assert items[0]["strain_name"] == "GMO"
    assert items[0]["strain_type"] is None  # no registry entry to pull a type from


def test_uses_linked_strain_registry_entry_when_available(db_session):
    strain = Strain(
        id="strain-1", name="GMO", lineage="Chemdog x GSC", strain_type="hybrid",
        thc_pct_typical=24.5, cbd_pct_typical=0.3,
    )
    db_session.add(strain)
    db_session.commit()
    make_harvest(db_session, strain="GMO", strain_id="strain-1")
    make_package(db_session)

    items = build_menu_items(db_session)
    assert items[0]["strain_name"] == "GMO"
    assert items[0]["strain_type"] == "hybrid"
    assert items[0]["lineage"] == "Chemdog x GSC"


def test_prefers_the_packages_own_lab_test_over_the_strains_typical_potency(db_session):
    strain = Strain(id="strain-1", name="GMO", thc_pct_typical=20.0, cbd_pct_typical=1.0)
    db_session.add(strain)
    db_session.commit()
    make_harvest(db_session, strain_id="strain-1")
    make_package(db_session)
    make_lab_test(db_session, "pkg-1", thc_pct=27.3, cbd_pct=0.2, tested_at=date(2026, 8, 1))

    items = build_menu_items(db_session)
    assert items[0]["thc_pct"] == 27.3
    assert items[0]["cbd_pct"] == 0.2


def test_falls_back_to_strain_typical_potency_when_package_has_no_lab_test(db_session):
    strain = Strain(id="strain-1", name="GMO", thc_pct_typical=20.0, cbd_pct_typical=1.0)
    db_session.add(strain)
    db_session.commit()
    make_harvest(db_session, strain_id="strain-1")
    make_package(db_session)

    items = build_menu_items(db_session)
    assert items[0]["thc_pct"] == 20.0
    assert items[0]["cbd_pct"] == 1.0


def test_uses_the_most_recent_passed_lab_test(db_session):
    make_harvest(db_session)
    make_package(db_session)
    make_lab_test(db_session, "pkg-1", thc_pct=20.0, cbd_pct=0.5, tested_at=date(2026, 6, 1))
    make_lab_test(db_session, "pkg-1", thc_pct=25.0, cbd_pct=0.4, tested_at=date(2026, 8, 1))

    items = build_menu_items(db_session)
    assert items[0]["thc_pct"] == 25.0


def test_a_failed_lab_test_is_ignored(db_session):
    make_harvest(db_session)
    make_package(db_session)
    make_lab_test(db_session, "pkg-1", thc_pct=99.0, cbd_pct=99.0, tested_at=date(2026, 8, 1), result="fail")

    items = build_menu_items(db_session)
    assert items[0]["thc_pct"] is None


def test_non_active_packages_are_excluded(db_session):
    make_harvest(db_session)
    package = make_package(db_session)
    package.status = "sold"
    db_session.commit()

    assert build_menu_items(db_session) == []


def test_price_and_weight_pass_through(db_session):
    make_harvest(db_session)
    make_package(db_session, price_cents=4500)

    items = build_menu_items(db_session)
    assert items[0]["price_cents"] == 4500
    assert items[0]["weight_g"] == 453.6
    assert items[0]["package_id"] == "pkg-1"
