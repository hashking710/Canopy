import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from canopy_agent.compliance_models import Operator
from canopy_agent.deps import get_db
from canopy_agent.services.audit import record_audit
from canopy_agent.services.operators import (
    KNOWN_ROLES,
    get_active_operator,
    pin_check_failed,
    require_role,
    set_pin,
    verify_pin,
)
from canopy_agent.services.security_settings import get_require_operator_pins, set_require_operator_pins

router = APIRouter(prefix="/api/operators", tags=["operators"])


class CreateOperatorRequest(BaseModel):
    name: str
    pin: str | None = None
    # New operators default to the lower "operator" tier, not "admin" — except the
    # very first operator a facility ever registers, which is always forced to
    # "admin" regardless of this value (see create_operator) — otherwise a brand
    # new facility has no operator with permission to grant anyone the admin role
    # that granting itself requires, a real deadlock, not a hypothetical one.
    role: str = "operator"
    # Notification preferences are self-service: whatever's submitted here is just
    # stored as-is, with no server-side role-based defaulting — a role-based
    # *suggestion* is a frontend nicety only (see OperatorPicker.tsx), never
    # enforced server-side.
    notify_email: str | None = None
    notify_on_alerts: bool = False
    notify_on_system_errors: bool = False
    notify_min_severity: str = "critical"


class UpdateNotificationPreferencesRequest(BaseModel):
    notify_email: str | None = None
    notify_on_alerts: bool = False
    notify_on_system_errors: bool = False
    notify_min_severity: str = "critical"


KNOWN_SEVERITIES = frozenset({"warning", "critical"})


def _operator_dict(operator: Operator) -> dict:
    return {
        "id": operator.id,
        "name": operator.name,
        "role": operator.role,
        "has_pin": bool(operator.pin_hash),
        "notify_email": operator.notify_email,
        "notify_on_alerts": operator.notify_on_alerts,
        "notify_on_system_errors": operator.notify_on_system_errors,
        "notify_min_severity": operator.notify_min_severity,
    }


class SetRoleRequest(BaseModel):
    role: str
    acting_operator_id: str
    # Security-review finding, fixed before shipping: an acting_operator_id alone
    # is just a string a caller supplies — it proves nothing about who is actually
    # making the request. Without also checking this operator's PIN (when they
    # have one configured; see pin_check_failed's own "no PIN configured means no
    # extra check" semantics), anyone who learns any admin's id — e.g. from GET
    # /api/operators, which lists every operator's role with no gating — could
    # cite that id to grant *their own* operator admin, a full bypass of every
    # role check this feature exists to enforce. Same PIN-if-configured pattern
    # secrets.py's _require_admin_operator already uses for exactly this reason.
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
    if body.role not in KNOWN_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(KNOWN_ROLES)}")
    if body.notify_min_severity not in KNOWN_SEVERITIES:
        raise HTTPException(status_code=400, detail=f"notify_min_severity must be one of {sorted(KNOWN_SEVERITIES)}")

    is_first_operator = db.execute(select(Operator.id).limit(1)).first() is None
    role = "admin" if is_first_operator else body.role

    operator = Operator(
        id=f"op-{uuid.uuid4().hex[:10]}", name=body.name, role=role,
        notify_email=body.notify_email, notify_on_alerts=body.notify_on_alerts,
        notify_on_system_errors=body.notify_on_system_errors, notify_min_severity=body.notify_min_severity,
    )
    if body.pin:
        set_pin(operator, body.pin)
    db.add(operator)
    db.commit()
    return _operator_dict(operator)


@router.get("")
def list_operators(db: Session = Depends(get_db)) -> list[dict]:
    operators = db.execute(select(Operator).where(Operator.active == True)).scalars().all()  # noqa: E712
    return [_operator_dict(o) for o in operators]


@router.put("/{operator_id}/notification-preferences")
def update_notification_preferences(
    operator_id: str, body: UpdateNotificationPreferencesRequest, db: Session = Depends(get_db)
) -> dict:
    """Self-service — personal preference data about the operator making the
    request, not a privileged action on someone else, so this doesn't gate on role
    the way e.g. set_operator_role does (mirrors reset_operator_pin's own
    simplicity for the same reason)."""
    operator = get_active_operator(db, operator_id)
    if operator is None:
        raise HTTPException(status_code=404, detail="operator not found")
    if body.notify_min_severity not in KNOWN_SEVERITIES:
        raise HTTPException(status_code=400, detail=f"notify_min_severity must be one of {sorted(KNOWN_SEVERITIES)}")

    operator.notify_email = body.notify_email
    operator.notify_on_alerts = body.notify_on_alerts
    operator.notify_on_system_errors = body.notify_on_system_errors
    operator.notify_min_severity = body.notify_min_severity
    db.commit()
    return _operator_dict(operator)


@router.post("/{operator_id}/role")
def set_operator_role(operator_id: str, body: SetRoleRequest, db: Session = Depends(get_db)) -> dict:
    if body.role not in KNOWN_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(KNOWN_ROLES)}")

    acting_operator = get_active_operator(db, body.acting_operator_id)
    if acting_operator is None:
        raise HTTPException(status_code=404, detail="acting operator not found or inactive")
    if pin_check_failed(acting_operator, body.pin):
        raise HTTPException(status_code=401, detail=f"PIN required or incorrect for operator '{acting_operator.name}'")
    require_role(acting_operator, "admin")

    operator = get_active_operator(db, operator_id)
    if operator is None:
        raise HTTPException(status_code=404, detail="operator not found")

    previous_role = operator.role
    operator.role = body.role
    record_audit(
        db, "facility", "facility", "operator_role_changed", acting_operator.name,
        details={"operator": operator.name, "from": previous_role, "to": body.role},
    )
    db.commit()
    return {"id": operator.id, "name": operator.name, "role": operator.role}


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
