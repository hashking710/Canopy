import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from canopy_agent.compliance_models import Operator
from canopy_agent.deps import get_db
from canopy_agent.services.audit import record_audit
from canopy_agent.services.operators import get_active_operator, set_pin, verify_pin
from canopy_agent.services.security_settings import get_require_operator_pins, set_require_operator_pins

router = APIRouter(prefix="/api/operators", tags=["operators"])


class CreateOperatorRequest(BaseModel):
    name: str
    pin: str | None = None


class VerifyPinRequest(BaseModel):
    pin: str


class ResetPinRequest(BaseModel):
    pin: str | None = None  # omit/empty to remove the PIN entirely


class SetPinPolicyRequest(BaseModel):
    require_operator_pins: bool
    operator_id: str


@router.post("")
def create_operator(body: CreateOperatorRequest, db: Session = Depends(get_db)) -> dict:
    existing = db.execute(select(Operator).where(Operator.name == body.name)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=400, detail=f"an operator named '{body.name}' already exists")
    if not body.pin and get_require_operator_pins(db):
        raise HTTPException(status_code=400, detail="a PIN is required for every operator at this facility")

    operator = Operator(id=f"op-{uuid.uuid4().hex[:10]}", name=body.name)
    if body.pin:
        set_pin(operator, body.pin)
    db.add(operator)
    db.commit()
    return {"id": operator.id, "name": operator.name, "has_pin": bool(operator.pin_hash)}


@router.get("")
def list_operators(db: Session = Depends(get_db)) -> list[dict]:
    operators = db.execute(select(Operator).where(Operator.active == True)).scalars().all()  # noqa: E712
    return [{"id": o.id, "name": o.name, "has_pin": bool(o.pin_hash)} for o in operators]


@router.post("/{operator_id}/verify-pin")
def verify_operator_pin(operator_id: str, body: VerifyPinRequest, db: Session = Depends(get_db)) -> dict:
    operator = get_active_operator(db, operator_id)
    if operator is None:
        raise HTTPException(status_code=404, detail="operator not found")
    return {"valid": verify_pin(operator, body.pin)}


@router.post("/{operator_id}/reset-pin")
def reset_operator_pin(operator_id: str, body: ResetPinRequest, db: Session = Depends(get_db)) -> dict:
    operator = get_active_operator(db, operator_id)
    if operator is None:
        raise HTTPException(status_code=404, detail="operator not found")
    if body.pin:
        set_pin(operator, body.pin)
    elif get_require_operator_pins(db):
        raise HTTPException(status_code=400, detail="PINs are required for every operator at this facility — cannot be removed")
    else:
        operator.pin_hash = None
        operator.pin_salt = None
    db.commit()
    return {"id": operator.id, "name": operator.name, "has_pin": bool(operator.pin_hash)}


@router.get("/pin-policy")
def get_pin_policy(db: Session = Depends(get_db)) -> dict:
    active = db.execute(select(Operator).where(Operator.active == True)).scalars().all()  # noqa: E712
    without_pin = sum(1 for o in active if not o.pin_hash)
    return {"require_operator_pins": get_require_operator_pins(db), "operators_without_pin": without_pin}


@router.post("/pin-policy")
def set_pin_policy(body: SetPinPolicyRequest, db: Session = Depends(get_db)) -> dict:
    operator = get_active_operator(db, body.operator_id)
    if operator is None:
        raise HTTPException(status_code=404, detail="operator not found")
    previous = get_require_operator_pins(db)
    set_require_operator_pins(db, body.require_operator_pins, operator.name)
    record_audit(
        db, "facility", "facility", "pin_policy_changed", operator.name,
        details={"from": previous, "to": body.require_operator_pins},
    )
    db.commit()
    return get_pin_policy(db)


@router.post("/{operator_id}/deactivate")
def deactivate_operator(operator_id: str, db: Session = Depends(get_db)) -> dict:
    # Deactivated, never deleted — past compliance actions attribute to this
    # operator's name (a snapshot string on each record, not a live foreign key), so
    # removing the row would leave nothing wrong, but keeping it lets this endpoint
    # stay a simple flag flip rather than needing to reason about historical integrity.
    operator = db.get(Operator, operator_id)
    if operator is None:
        raise HTTPException(status_code=404, detail="operator not found")
    operator.active = False
    db.commit()
    return {"id": operator.id, "name": operator.name, "active": operator.active}
