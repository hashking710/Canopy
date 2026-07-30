from datetime import date, datetime, timedelta, timezone

from canopy_agent.compliance_models import Plant, PlantBatch, PhysicalCount
from canopy_agent.services.reconciliation import (
    latest_physical_counts,
    system_plant_count,
    system_plant_counts,
)

TODAY = date(2026, 1, 1)


def _plant(id: str, room_id: str, batch_id: str, status: str = "active") -> Plant:
    return Plant(
        id=id,
        room_id=room_id,
        batch_id=batch_id,
        strain="OG",
        growth_phase="Vegetative",
        planted_date=TODAY,
        tagged_date=TODAY,
        status=status,
    )


def _batch(id: str, room_id: str, untracked_count: int) -> PlantBatch:
    return PlantBatch(
        id=id,
        name=id,
        batch_type="Clone",
        strain="OG",
        room_id=room_id,
        planted_date=TODAY,
        untracked_count=untracked_count,
        status="active",
    )


def test_system_plant_counts_matches_the_single_room_function(db_session):
    db_session.add_all(
        [
            _plant("p1", "room-a", "b1"),
            _plant("p2", "room-a", "b1"),
            _plant("p3", "room-b", "b2", status="destroyed"),
            _batch("b1", "room-a", untracked_count=3),
            _batch("b2", "room-b", untracked_count=5),
        ]
    )
    db_session.commit()

    batch = system_plant_counts(db_session, ["room-a", "room-b"])

    assert batch["room-a"] == system_plant_count(db_session, "room-a") == 5  # 2 tagged + 3 untracked
    assert batch["room-b"] == system_plant_count(db_session, "room-b") == 5  # 0 active tagged + 5 untracked


def test_system_plant_counts_empty_input(db_session):
    assert system_plant_counts(db_session, []) == {}


def test_latest_physical_counts_returns_the_most_recent_row_per_room(db_session):
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            PhysicalCount(
                room_id="room-a", counted_value=10, system_value_at_time=10, counted_at=now - timedelta(days=2)
            ),
            PhysicalCount(room_id="room-a", counted_value=12, system_value_at_time=12, counted_at=now),  # newest
            PhysicalCount(room_id="room-b", counted_value=7, system_value_at_time=7, counted_at=now),
        ]
    )
    db_session.commit()

    result = latest_physical_counts(db_session, ["room-a", "room-b"])

    assert result["room-a"].counted_value == 12
    assert result["room-b"].counted_value == 7


def test_latest_physical_counts_omits_rooms_with_no_counts(db_session):
    result = latest_physical_counts(db_session, ["room-empty"])
    assert result == {}


def test_latest_physical_counts_empty_input(db_session):
    assert latest_physical_counts(db_session, []) == {}
