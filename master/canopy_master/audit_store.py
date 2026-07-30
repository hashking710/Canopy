from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from canopy_master.models import RelayedAuditEntry


def record_relayed_event(db: Session, site_id: str, payload: dict) -> bool:
    """Persists one audit-relay event durably. Returns True if this was newly
    recorded, False if already seen (idempotent — see RelayedAuditEntry's docstring
    on why: MQTT QoS 1 redelivers on reconnect, so the same message can arrive more
    than once)."""
    existing = db.execute(
        select(RelayedAuditEntry).where(
            RelayedAuditEntry.site_id == site_id,
            RelayedAuditEntry.origin_device_id == payload["origin_device_id"],
            RelayedAuditEntry.origin_entry_id == payload["id"],
        )
    ).scalar_one_or_none()
    if existing is not None:
        return False

    db.add(
        RelayedAuditEntry(
            site_id=site_id,
            origin_device_id=payload["origin_device_id"],
            origin_entry_id=payload["id"],
            entity_type=payload["entity_type"],
            entity_id=payload["entity_id"],
            action=payload["action"],
            actor=payload["actor"],
            room_id=payload.get("room_id"),
            details=payload.get("details") or {},
            occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            entry_hash=payload["entry_hash"],
        )
    )
    db.commit()
    return True


def list_relayed_events(db: Session, site_id: str | None = None, limit: int = 100) -> list[RelayedAuditEntry]:
    query = select(RelayedAuditEntry).order_by(RelayedAuditEntry.occurred_at.desc()).limit(limit)
    if site_id:
        query = query.where(RelayedAuditEntry.site_id == site_id)
    return list(db.execute(query).scalars().all())
