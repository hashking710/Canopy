import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from canopy_agent.compliance_models import Strain
from canopy_agent.compliance_serialize import model_to_dict
from canopy_agent.deps import get_db
from canopy_agent.services.operators import resolve_operator_with_role

router = APIRouter(prefix="/api/strains", tags=["strains"])

KNOWN_STRAIN_TYPES = frozenset({"indica", "sativa", "hybrid", "unknown"})


class CreateStrainRequest(BaseModel):
    name: str
    lineage: str = ""
    strain_type: str = "unknown"
    description: str = ""
    thc_pct_typical: float | None = None
    cbd_pct_typical: float | None = None
    operator_id: str


class UpdateStrainRequest(BaseModel):
    name: str | None = None
    lineage: str | None = None
    strain_type: str | None = None
    description: str | None = None
    thc_pct_typical: float | None = None
    cbd_pct_typical: float | None = None
    operator_id: str


def _validate_strain_type(strain_type: str) -> None:
    if strain_type not in KNOWN_STRAIN_TYPES:
        raise HTTPException(status_code=400, detail=f"strain_type must be one of {sorted(KNOWN_STRAIN_TYPES)}")


@router.post("")
def create_strain(body: CreateStrainRequest, db: Session = Depends(get_db)) -> dict:
    resolve_operator_with_role(db, body.operator_id, "operator")
    _validate_strain_type(body.strain_type)

    existing = db.execute(select(Strain).where(Strain.name == body.name)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=400, detail=f"a strain named '{body.name}' already exists")

    strain = Strain(
        id=f"strain-{uuid.uuid4().hex[:10]}",
        name=body.name,
        lineage=body.lineage,
        strain_type=body.strain_type,
        description=body.description,
        thc_pct_typical=body.thc_pct_typical,
        cbd_pct_typical=body.cbd_pct_typical,
    )
    db.add(strain)
    db.commit()
    return model_to_dict(strain)


@router.get("")
def list_strains(db: Session = Depends(get_db)) -> list[dict]:
    strains = db.execute(select(Strain).where(Strain.active == True)).scalars().all()  # noqa: E712
    return [model_to_dict(s) for s in strains]


@router.put("/{strain_id}")
def update_strain(strain_id: str, body: UpdateStrainRequest, db: Session = Depends(get_db)) -> dict:
    resolve_operator_with_role(db, body.operator_id, "operator")

    strain = db.get(Strain, strain_id)
    if strain is None:
        raise HTTPException(status_code=404, detail="strain not found")

    if body.strain_type is not None:
        _validate_strain_type(body.strain_type)
    if body.name is not None:
        existing = db.execute(
            select(Strain).where(Strain.name == body.name, Strain.id != strain_id)
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(status_code=400, detail=f"a strain named '{body.name}' already exists")

    # operator_id isn't a Strain column — exclude it before the generic setattr loop,
    # same reasoning as routers/rooms.py's update_room.
    updates = body.model_dump(exclude_unset=True, exclude={"operator_id"})
    for key, value in updates.items():
        setattr(strain, key, value)
    db.commit()
    return model_to_dict(strain)


@router.post("/{strain_id}/deactivate")
def deactivate_strain(strain_id: str, operator_id: str, db: Session = Depends(get_db)) -> dict:
    resolve_operator_with_role(db, operator_id, "operator")

    strain = db.get(Strain, strain_id)
    if strain is None:
        raise HTTPException(status_code=404, detail="strain not found")
    strain.active = False
    db.commit()
    return {"id": strain.id, "active": strain.active}
