from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from canopy_agent.compliance_models import Plant, PlantBatch, PhysicalCount


def system_plant_count(db: Session, room_id: str) -> int:
    """
    Live count of everything the system considers 'in this room right now':
    individually tagged active plants, plus only the *untracked* count still sitting
    in active plant batches there. `PlantBatch.tracked_count` is deliberately excluded
    — it's a redundant summary of plants that already exist as their own `Plant` rows
    (created by /tag-plants), so including it would double-count them.
    """
    plant_count = db.execute(
        select(func.count()).select_from(Plant).where(Plant.room_id == room_id, Plant.status == "active")
    ).scalar_one()

    untracked_counts = db.execute(
        select(func.sum(PlantBatch.untracked_count)).where(
            PlantBatch.room_id == room_id, PlantBatch.status == "active"
        )
    ).scalar_one()

    return plant_count + (untracked_counts or 0)


def system_plant_counts(db: Session, room_ids: list[str]) -> dict[str, int]:
    """Same as system_plant_count, but for every room in two grouped queries instead
    of two queries per room — used by the reconciliation endpoint, which needs this
    for every active room on every page load, not just one room at a time."""
    if not room_ids:
        return {}

    plant_counts = dict(
        db.execute(
            select(Plant.room_id, func.count())
            .where(Plant.room_id.in_(room_ids), Plant.status == "active")
            .group_by(Plant.room_id)
        ).all()
    )
    untracked_counts = dict(
        db.execute(
            select(PlantBatch.room_id, func.sum(PlantBatch.untracked_count))
            .where(PlantBatch.room_id.in_(room_ids), PlantBatch.status == "active")
            .group_by(PlantBatch.room_id)
        ).all()
    )
    return {room_id: plant_counts.get(room_id, 0) + (untracked_counts.get(room_id) or 0) for room_id in room_ids}


def latest_physical_counts(db: Session, room_ids: list[str]) -> dict[str, PhysicalCount]:
    """Most recent PhysicalCount row per room, for every room in one query instead of
    one query per room — same latest-row-per-group shape as stats.py's
    get_latest_values_for_rooms."""
    if not room_ids:
        return {}

    latest_ts = (
        select(PhysicalCount.room_id, func.max(PhysicalCount.counted_at).label("counted_at"))
        .where(PhysicalCount.room_id.in_(room_ids))
        .group_by(PhysicalCount.room_id)
        .subquery()
    )
    rows = (
        db.execute(
            select(PhysicalCount).join(
                latest_ts,
                (PhysicalCount.room_id == latest_ts.c.room_id) & (PhysicalCount.counted_at == latest_ts.c.counted_at),
            )
        )
        .scalars()
        .all()
    )
    return {row.room_id: row for row in rows}


def is_recount_stale(last_counted_at: datetime, cadence_days: float | None, now: datetime | None = None) -> bool:
    """
    True if a room's last physical count is older than the active state's mandated
    reconciliation cadence (e.g. Colorado requires daily counts — see
    compliance_rules/colorado.py). cadence_days=None means no such requirement was
    found for the active state, so staleness never applies.
    """
    if cadence_days is None:
        return False
    now = now or datetime.now(timezone.utc)
    if last_counted_at.tzinfo is None:  # SQLite round-trips DateTime columns as naive
        last_counted_at = last_counted_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return (now - last_counted_at).total_seconds() > cadence_days * 86400
