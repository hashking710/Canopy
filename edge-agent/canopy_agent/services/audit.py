import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from canopy_agent.compliance_models import AuditLogEntry, utcnow

GENESIS_HASH = "0" * 64


def _normalize_ts(occurred_at: datetime) -> str:
    # SQLite round-trips DateTime columns as naive (see e.g. services/retention.py's
    # same note), so a tz-aware value computed at write time and the naive value read
    # back later must normalize to the same string, or verify_audit_chain would flag
    # every single entry as "tampered" purely from that round-trip, not real tampering.
    if occurred_at.tzinfo is not None:
        occurred_at = occurred_at.astimezone(timezone.utc).replace(tzinfo=None)
    return occurred_at.isoformat()


def _compute_entry_hash(
    prev_hash: str,
    entity_type: str,
    entity_id: str,
    action: str,
    actor: str,
    room_id: str | None,
    details: dict,
    occurred_at: datetime,
) -> str:
    payload = json.dumps(
        {
            "prev_hash": prev_hash,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "actor": actor,
            "room_id": room_id,
            "details": details,
            "occurred_at": _normalize_ts(occurred_at),
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def record_audit(
    db: Session,
    entity_type: str,
    entity_id: str,
    action: str,
    actor: str,
    room_id: str | None = None,
    details: dict | None = None,
) -> AuditLogEntry:
    """
    Write one chain-of-custody entry, hash-chained to the one before it — see
    AuditLogEntry's docstring for why. Every compliance-mutating endpoint calls this;
    the point of a single narrow helper is that there is exactly one place "what
    counts as an auditable action" is decided, so nothing mutates compliance state
    silently.
    """
    details = details or {}
    occurred_at = utcnow()

    prev_entry = db.execute(select(AuditLogEntry).order_by(AuditLogEntry.id.desc()).limit(1)).scalar_one_or_none()
    prev_hash = prev_entry.entry_hash if prev_entry else GENESIS_HASH

    entry_hash = _compute_entry_hash(prev_hash, entity_type, entity_id, action, actor, room_id, details, occurred_at)

    entry = AuditLogEntry(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        room_id=room_id,
        details=details,
        occurred_at=occurred_at,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
    )
    db.add(entry)
    db.flush()  # so a subsequent record_audit call in the same transaction sees this as `prev`
    return entry


def verify_audit_chain(db: Session) -> list[int]:
    """
    Returns the ids of entries that don't match what the hash chain says they should
    be — i.e. tampered with (or, in principle, a chain corrupted some other way). An
    empty list means the entire audit trail is provably intact from the first entry.
    """
    entries = db.execute(select(AuditLogEntry).order_by(AuditLogEntry.id)).scalars().all()
    broken: list[int] = []
    expected_prev_hash = GENESIS_HASH
    for entry in entries:
        recomputed_hash = _compute_entry_hash(
            expected_prev_hash, entry.entity_type, entry.entity_id, entry.action, entry.actor,
            entry.room_id, entry.details, entry.occurred_at,
        )
        if entry.prev_hash != expected_prev_hash or entry.entry_hash != recomputed_hash:
            broken.append(entry.id)
        # Continue the chain from the *recorded* hash regardless, so a single edited
        # entry is reported once, not as a cascade of "every entry after it" too.
        expected_prev_hash = entry.entry_hash
    return broken
