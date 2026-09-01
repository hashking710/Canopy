import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import Integer, delete, func, select
from sqlalchemy.orm import Session

from canopy_agent.db import SessionLocal
from canopy_agent.models import Reading, ReadingRollup
from canopy_agent.services.error_reporting import report_system_error

logger = logging.getLogger("canopy_agent.retention")

RAW_RETENTION_DAYS = 7
# Only roll up buckets safely in the past — a hour bucket that's still receiving
# writes must never be aggregated and pruned prematurely.
ROLLUP_DELAY_MINUTES = 65
RETENTION_CYCLE_INTERVAL_SECONDS = 3600


async def retention_forever() -> None:
    while True:
        db = SessionLocal()
        try:
            stats = run_retention_cycle(db)
            if stats["buckets_rolled_up"] or stats["raw_readings_pruned"]:
                logger.info("retention cycle: %s", stats)
        except Exception as exc:
            logger.exception("retention cycle failed")
            # No UI surfacing at all for this one (unlike a room's poll failure) —
            # a run failing silently for weeks would just mean unbounded DB growth
            # on a Pi's limited storage until someone happens to notice.
            await report_system_error("retention", "retention cycle failed", exc)
        finally:
            db.close()
        await asyncio.sleep(RETENTION_CYCLE_INTERVAL_SECONDS)


def run_retention_cycle(db: Session, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    rolled_up = _rollup_pending_readings(db, now)
    pruned = _prune_old_raw_readings(db, now)
    db.commit()
    return {"buckets_rolled_up": rolled_up, "raw_readings_pruned": pruned}


def _rollup_pending_readings(db: Session, now: datetime) -> int:
    """
    Aggregates entirely in SQL (GROUP BY + AVG/MIN/MAX/COUNT) rather than pulling every
    raw Reading row into Python and grouping by hand — the previous version hydrated
    every matching row as a full ORM object and did the aggregation in a Python
    defaultdict, which is O(raw readings) in both time and memory. At a real
    deployment's polling cadence (every few seconds, many rooms, running for weeks)
    that backlog reaches millions of rows, and this cycle runs on every single
    process restart (not just hourly) — a slow first cycle isn't a minor inefficiency,
    it's a multi-minute startup freeze (this blocks the whole event loop; see
    retention_forever's docstring). Grouping in SQL instead means Python only ever
    touches one row per (room, metric, hour) — thousands at most, not millions.
    """
    cutoff = now - timedelta(minutes=ROLLUP_DELAY_MINUTES)

    existing_buckets = {
        (r.room_id, r.metric, r.bucket_start) for r in db.execute(select(ReadingRollup)).scalars().all()
    }

    # SQLite has no built-in "truncate to the hour" function — convert to Unix-epoch
    # seconds, floor-divide down to the hour, then back to a real datetime string.
    # Portable regardless of exactly how SQLAlchemy's SQLite dialect serializes
    # DateTime, since strftime('%s', ...) accepts any of SQLite's recognized
    # time-string formats.
    epoch_seconds = func.cast(func.strftime("%s", Reading.ts), Integer)
    # .op("/") rather than plain `/` — SQLAlchemy promotes integer-column division to
    # floating point by default (a correctness bug caught by this file's own tests: it
    # silently stopped truncating to the hour at all, since dividing and re-multiplying
    # a float by 3600 just returns ~the original value). SQLite's native `/` between
    # two actual INTEGERs floors — .op() emits it as bare SQL text instead of letting
    # SQLAlchemy's type system reinterpret it.
    bucket_start_expr = func.datetime(epoch_seconds.op("/")(3600).op("*")(3600), "unixepoch").label("bucket_start")

    grouped = db.execute(
        select(
            Reading.room_id,
            Reading.metric,
            bucket_start_expr,
            func.avg(Reading.value),
            func.min(Reading.value),
            func.max(Reading.value),
            func.count(Reading.value),
        )
        .where(Reading.ts < cutoff)
        .group_by(Reading.room_id, Reading.metric, bucket_start_expr)
    ).all()

    created = 0
    for room_id, metric, bucket_start_str, avg_value, min_value, max_value, sample_count in grouped:
        bucket_start = datetime.fromisoformat(bucket_start_str)
        if (room_id, metric, bucket_start) in existing_buckets:
            continue
        db.add(
            ReadingRollup(
                room_id=room_id,
                metric=metric,
                bucket_start=bucket_start,
                avg_value=avg_value,
                min_value=min_value,
                max_value=max_value,
                sample_count=sample_count,
            )
        )
        created += 1
    if created:
        db.flush()  # so _prune_old_raw_readings (called right after, same transaction) sees these new rollups
    return created


def _prune_old_raw_readings(db: Session, now: datetime) -> int:
    """
    Deletes by (room, metric, hour-bucket) range rather than hydrating every candidate
    raw Reading row into Python to check set membership one at a time — same fix as
    _rollup_pending_readings, for the same reason: the old version was O(raw readings),
    this one is O(rolled-up buckets), which is smaller by exactly the polling-interval
    factor (readings-per-hour-per-series).
    """
    cutoff = now - timedelta(days=RAW_RETENTION_DAYS)

    rolled_up_buckets = db.execute(
        select(ReadingRollup.room_id, ReadingRollup.metric, ReadingRollup.bucket_start)
        .where(ReadingRollup.bucket_start < cutoff)
    ).all()

    pruned = 0
    for room_id, metric, bucket_start in rolled_up_buckets:
        bucket_end = bucket_start + timedelta(hours=1)
        result = db.execute(
            delete(Reading).where(
                Reading.room_id == room_id,
                Reading.metric == metric,
                Reading.ts >= bucket_start,
                Reading.ts < bucket_end,
            )
        )
        pruned += result.rowcount
    return pruned
