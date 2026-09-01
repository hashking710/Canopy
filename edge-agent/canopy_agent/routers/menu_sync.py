import os

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from canopy_agent.deps import get_db
from canopy_agent.menu_sync.registry import available_sync_types
from canopy_agent.services.menu_sync_status import get_menu_sync_status
from canopy_agent.services.menu_sync_task import run_menu_sync_once
from canopy_agent.services.operators import resolve_operator_with_role

router = APIRouter(prefix="/api/menu-sync", tags=["menu-sync"])


def _iso(dt) -> str | None:
    return dt.isoformat() if dt is not None else None


@router.get("/status")
def menu_sync_status(db: Session = Depends(get_db)) -> dict:
    active_type = os.environ.get("CANOPY_MENU_SYNC", "null")
    status = get_menu_sync_status(db)
    return {
        "active_provider": active_type,
        "available_providers": [
            {"type": name, "plugin_name": cls.plugin_name, "plugin_description": cls.plugin_description}
            for name, cls in sorted(available_sync_types().items())
        ],
        "last_synced_at": _iso(status.last_synced_at),
        "last_result": status.last_result,
        "last_error": status.last_error,
    }


@router.post("/run")
async def run_menu_sync_now(operator_id: str, db: Session = Depends(get_db)) -> dict:
    resolve_operator_with_role(db, operator_id, "operator")
    return await run_menu_sync_once(db)
