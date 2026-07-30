from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from canopy_agent.models import Reading, ReadingRollup, Room
from canopy_agent.services.retention import run_retention_cycle


def make_room(db_session, room_id="test-room"):
    room = Room(id=room_id, room_type="greenhouse", path=f"~/{room_id}", metric_config={})
    db_session.add(room)
    db_session.commit()
    return room


def add_reading(db_session, room_id, metric, value, ts):
    db_session.add(Reading(room_id=room_id, metric=metric, value=value, ts=ts))


def test_rollup_creates_bucket_for_old_readings(db_session):
    make_room(db_session)
    now = datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc)
    bucket_hour = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)  # well past the rollup delay
    for minute, value in [(5, 70.0), (35, 74.0), (55, 72.0)]:
        add_reading(db_session, "test-room", "temp_f", value, bucket_hour + timedelta(minutes=minute))
    db_session.commit()

    stats = run_retention_cycle(db_session, now=now)

    assert stats["buckets_rolled_up"] == 1
    rollup = db_session.execute(select(ReadingRollup)).scalar_one()
    assert rollup.bucket_start == bucket_hour.replace(tzinfo=None)  # SQLite round-trips DateTime as naive
    assert rollup.sample_count == 3
    assert rollup.min_value == 70.0
    assert rollup.max_value == 74.0
    assert rollup.avg_value == 72.0


def test_recent_readings_are_not_rolled_up_yet(db_session):
    make_room(db_session)
    now = datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc)
    add_reading(db_session, "test-room", "temp_f", 70.0, now - timedelta(minutes=10))
    db_session.commit()

    stats = run_retention_cycle(db_session, now=now)

    assert stats["buckets_rolled_up"] == 0
    assert db_session.execute(select(ReadingRollup)).first() is None


def test_prune_only_deletes_readings_with_a_rollup(db_session):
    make_room(db_session)
    now = datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc)

    old_and_rollable = now - timedelta(days=10)
    old_but_too_recent_to_rollup_yet = now - timedelta(minutes=5)  # inside the rollup delay window

    add_reading(db_session, "test-room", "temp_f", 70.0, old_and_rollable)
    add_reading(db_session, "test-room", "temp_f", 71.0, old_but_too_recent_to_rollup_yet)
    db_session.commit()

    stats = run_retention_cycle(db_session, now=now)

    assert stats["buckets_rolled_up"] == 1
    assert stats["raw_readings_pruned"] == 1

    remaining = db_session.execute(select(Reading)).scalars().all()
    assert len(remaining) == 1
    assert remaining[0].ts == old_but_too_recent_to_rollup_yet.replace(tzinfo=None)


def test_rollup_correctly_separates_multiple_rooms_metrics_and_hours(db_session):
    # Regression guard for the SQL-side GROUP BY rewrite specifically: readings from
    # different rooms, different metrics, and different hours must never collapse into
    # the same rollup bucket just because they're aggregated in one query now instead
    # of a hand-rolled Python dict keyed the same way.
    make_room(db_session, "room-a")
    make_room(db_session, "room-b")
    now = datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc)
    hour_1 = datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)
    hour_2 = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)

    add_reading(db_session, "room-a", "temp_f", 70.0, hour_1 + timedelta(minutes=1))
    add_reading(db_session, "room-a", "temp_f", 72.0, hour_1 + timedelta(minutes=2))
    add_reading(db_session, "room-a", "rh_pct", 50.0, hour_1 + timedelta(minutes=1))
    add_reading(db_session, "room-a", "temp_f", 80.0, hour_2 + timedelta(minutes=1))
    add_reading(db_session, "room-b", "temp_f", 60.0, hour_1 + timedelta(minutes=1))
    db_session.commit()

    stats = run_retention_cycle(db_session, now=now)

    assert stats["buckets_rolled_up"] == 4  # (room-a,temp_f,h1) (room-a,rh_pct,h1) (room-a,temp_f,h2) (room-b,temp_f,h1)
    rollups = {(r.room_id, r.metric, r.bucket_start): r for r in db_session.execute(select(ReadingRollup)).scalars().all()}
    room_a_temp_h1 = rollups[("room-a", "temp_f", hour_1.replace(tzinfo=None))]
    assert room_a_temp_h1.sample_count == 2
    assert room_a_temp_h1.avg_value == 71.0
    assert rollups[("room-a", "rh_pct", hour_1.replace(tzinfo=None))].sample_count == 1
    assert rollups[("room-a", "temp_f", hour_2.replace(tzinfo=None))].sample_count == 1
    assert rollups[("room-b", "temp_f", hour_1.replace(tzinfo=None))].sample_count == 1


def test_rollup_handles_a_large_backlog_across_many_hours(db_session):
    # Not a timing assertion (those are flaky) — a correctness guard at a scale big
    # enough that the old Python-side groupby-by-hand approach would be genuinely slow
    # (this is exactly the shape of backlog that caused a real multi-minute startup
    # freeze at ~1.7M rows in practice): many hours' worth of readings, rolled up in
    # one SQL-aggregated pass, must still produce exactly the right bucket count and
    # exactly the right per-bucket statistics.
    make_room(db_session)
    now = datetime(2026, 1, 20, 0, 0, tzinfo=timezone.utc)
    start = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)
    hours = 50
    readings_per_hour = 20
    for hour in range(hours):
        bucket = start + timedelta(hours=hour)
        for minute in range(readings_per_hour):
            add_reading(db_session, "test-room", "temp_f", float(minute), bucket + timedelta(minutes=minute))
    db_session.commit()

    stats = run_retention_cycle(db_session, now=now)

    assert stats["buckets_rolled_up"] == hours
    rollups = db_session.execute(select(ReadingRollup)).scalars().all()
    assert len(rollups) == hours
    assert all(r.sample_count == readings_per_hour for r in rollups)
    expected_avg = sum(range(readings_per_hour)) / readings_per_hour
    assert all(r.avg_value == expected_avg for r in rollups)


def test_second_cycle_does_not_duplicate_rollups(db_session):
    make_room(db_session)
    now = datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc)
    add_reading(db_session, "test-room", "temp_f", 70.0, now - timedelta(days=1))
    db_session.commit()

    run_retention_cycle(db_session, now=now)
    second_stats = run_retention_cycle(db_session, now=now + timedelta(hours=1))

    assert second_stats["buckets_rolled_up"] == 0
    assert db_session.execute(select(ReadingRollup)).scalars().all().__len__() == 1
