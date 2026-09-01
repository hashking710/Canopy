import asyncio
import logging
import os

from sqlalchemy.orm import Session

from canopy_agent.db import SessionLocal
from canopy_agent.menu_sync.registry import get_menu_sync
from canopy_agent.services.error_reporting import report_system_error
from canopy_agent.services.health import record_failure, record_success
from canopy_agent.services.menu_data import build_menu_items
from canopy_agent.services.menu_sync_status import record_menu_sync_failure, record_menu_sync_success

logger = logging.getLogger("canopy_agent.menu_sync_task")

MENU_SYNC_INTERVAL_SECONDS = int(os.environ.get("CANOPY_MENU_SYNC_INTERVAL_SECONDS", "900"))


async def menu_sync_forever() -> None:
    while True:
        db = SessionLocal()
        try:
            result = await run_menu_sync_once(db)
            logger.info("menu sync cycle: %s", result)
            record_success("menu_sync")
        except Exception as exc:
            logger.exception("menu sync cycle failed")
            record_failure("menu_sync")
            record_menu_sync_failure(db, str(exc) or exc.__class__.__name__)
            # A silently-stale menu (stopped updating weeks ago) is exactly the kind
            # of failure that's invisible without this — same reasoning as every
            # other background task's own report_system_error call.
            await report_system_error("menu_sync", "menu sync cycle failed", exc)
        finally:
            db.close()
        await asyncio.sleep(MENU_SYNC_INTERVAL_SECONDS)


async def run_menu_sync_once(db: Session) -> dict:
    items = build_menu_items(db)
    result = await get_menu_sync().push_menu(items)
    record_menu_sync_success(db, result)
    return result
