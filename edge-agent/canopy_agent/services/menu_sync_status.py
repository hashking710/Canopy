from sqlalchemy.orm import Session

from canopy_agent.compliance_models import MenuSyncStatus, utcnow

MENU_SYNC_STATUS_ROW_ID = "menu_sync"


def get_menu_sync_status(db: Session) -> MenuSyncStatus:
    row = db.get(MenuSyncStatus, MENU_SYNC_STATUS_ROW_ID)
    if row is None:
        row = MenuSyncStatus(id=MENU_SYNC_STATUS_ROW_ID)
        db.add(row)
        db.commit()
    return row


def record_menu_sync_success(db: Session, result: dict) -> None:
    row = get_menu_sync_status(db)
    row.last_synced_at = utcnow()
    row.last_result = result
    row.last_error = None
    db.commit()


def record_menu_sync_failure(db: Session, error: str) -> None:
    row = get_menu_sync_status(db)
    row.last_error = error
    db.commit()
