from fastapi import APIRouter

from canopy_agent.services.backup import list_backups, run_backup

router = APIRouter(prefix="/api/backup", tags=["backup"])


def _serialize(result) -> dict:
    return {
        "filename": result.path.name,
        "size_bytes": result.size_bytes,
        "created_at": result.created_at.isoformat(),
    }


@router.get("/status")
def get_backup_status() -> dict:
    """Surfaces whether backups are actually happening, not just configured — an
    operator relying on this for disaster recovery needs to be able to see the last
    successful snapshot without SSHing into the device and reading logs."""
    backups = list_backups()
    latest = backups[-1] if backups else None
    return {
        "count": len(backups),
        "latest": _serialize(latest) if latest else None,
        "backups": [_serialize(b) for b in backups],
    }


@router.post("/run")
def trigger_backup_now() -> dict:
    """Manual trigger — same function the scheduled loop calls, just invoked on
    demand (e.g. right before a risky bulk operation, or to verify the mechanism
    works at all rather than waiting up to a day for the first scheduled run)."""
    return _serialize(run_backup())
