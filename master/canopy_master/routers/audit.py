from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from canopy_master.audit_store import list_relayed_events
from canopy_master.deps import get_db
from canopy_master.models import RelayedAuditEntry

router = APIRouter(prefix="/api/audit-log", tags=["audit"])


def _serialize(entry: RelayedAuditEntry) -> dict:
    return {
        "id": entry.id,
        "site_id": entry.site_id,
        "origin_device_id": entry.origin_device_id,
        "origin_entry_id": entry.origin_entry_id,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "action": entry.action,
        "actor": entry.actor,
        "room_id": entry.room_id,
        "details": entry.details,
        "occurred_at": entry.occurred_at.isoformat(),
        "entry_hash": entry.entry_hash,
        "received_at": entry.received_at.isoformat(),
    }


@router.get("")
def get_audit_log(site_id: str | None = None, limit: int = 100, db: Session = Depends(get_db)) -> list[dict]:
    """The consolidated, cross-device (and, once more than one site reports in,
    cross-site) audit trail this master instance has relayed and durably stored — see
    RelayedAuditEntry's docstring. Optionally filtered to one site."""
    return [_serialize(e) for e in list_relayed_events(db, site_id, limit)]
