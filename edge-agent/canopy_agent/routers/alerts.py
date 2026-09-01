import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from canopy_agent.compliance_serialize import model_to_dict
from canopy_agent.deps import get_db
from canopy_agent.models import AlertEvent, AlertRule
from canopy_agent.services.operators import get_active_operator, require_role, resolve_operator_with_role

router = APIRouter(prefix="/api", tags=["alerts"])


class CreateAlertRuleRequest(BaseModel):
    room_id: str
    metric: str
    condition: str  # "gt" | "lt"
    threshold: float
    severity: str = "warning"  # "warning" | "critical"
    operator_id: str


class AcknowledgeAlertRequest(BaseModel):
    operator_id: str


@router.post("/alert-rules")
def create_alert_rule(body: CreateAlertRuleRequest, db: Session = Depends(get_db)) -> dict:
    resolve_operator_with_role(db, body.operator_id, "operator")
    if body.condition not in ("gt", "lt"):
        raise HTTPException(status_code=400, detail="condition must be 'gt' or 'lt'")
    rule = AlertRule(
        id=f"rule-{uuid.uuid4().hex[:10]}",
        room_id=body.room_id,
        metric=body.metric,
        condition=body.condition,
        threshold=body.threshold,
        severity=body.severity,
    )
    db.add(rule)
    db.commit()
    return model_to_dict(rule)


@router.get("/alert-rules")
def list_alert_rules(room_id: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    query = select(AlertRule)
    if room_id:
        query = query.where(AlertRule.room_id == room_id)
    return [model_to_dict(r) for r in db.execute(query).scalars().all()]


@router.delete("/alert-rules/{rule_id}")
def delete_alert_rule(rule_id: str, operator_id: str, db: Session = Depends(get_db)) -> dict:
    resolve_operator_with_role(db, operator_id, "operator")
    rule = db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="alert rule not found")
    db.delete(rule)
    db.commit()
    return {"deleted": rule_id}


@router.get("/alert-events")
def list_alert_events(active_only: bool = False, db: Session = Depends(get_db)) -> list[dict]:
    query = select(AlertEvent).order_by(AlertEvent.triggered_at.desc())
    if active_only:
        query = query.where(AlertEvent.resolved_at.is_(None))
    return [model_to_dict(e) for e in db.execute(query).scalars().all()]


@router.post("/alert-events/{event_id}/acknowledge")
def acknowledge_alert_event(event_id: int, body: AcknowledgeAlertRequest, db: Session = Depends(get_db)) -> dict:
    operator = get_active_operator(db, body.operator_id)
    if operator is None:
        raise HTTPException(status_code=404, detail=f"operator '{body.operator_id}' not found or inactive")
    require_role(operator, "operator")
    event = db.get(AlertEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="alert event not found")
    event.acknowledged_at = datetime.now(timezone.utc)
    event.acknowledged_by = operator.name
    db.commit()
    return model_to_dict(event)
