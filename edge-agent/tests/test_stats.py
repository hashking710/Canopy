from datetime import datetime, timedelta, timezone

from canopy_agent.models import Reading, Room
from canopy_agent.stats import get_latest_values, get_latest_values_for_rooms


def _room(db, room_id: str) -> Room:
    room = Room(id=room_id, room_type="greenhouse", path=f"~/{room_id}", metric_config={})
    db.add(room)
    db.commit()
    return room


def test_get_latest_values_for_rooms_returns_the_most_recent_value_per_metric(db_session):
    _room(db_session, "room-a")
    _room(db_session, "room-b")
    now = datetime.now(timezone.utc)

    db_session.add_all(
        [
            Reading(room_id="room-a", metric="temp_f", value=70.0, ts=now - timedelta(minutes=2)),
            Reading(room_id="room-a", metric="temp_f", value=75.0, ts=now),  # newest — should win
            Reading(room_id="room-a", metric="rh_pct", value=50.0, ts=now),
            Reading(room_id="room-b", metric="temp_f", value=68.0, ts=now),
        ]
    )
    db_session.commit()

    result = get_latest_values_for_rooms(db_session, ["room-a", "room-b"])

    assert result["room-a"] == {"temp_f": 75.0, "rh_pct": 50.0}
    assert result["room-b"] == {"temp_f": 68.0}


def test_get_latest_values_for_rooms_includes_rooms_with_no_readings(db_session):
    _room(db_session, "room-empty")

    result = get_latest_values_for_rooms(db_session, ["room-empty"])

    assert result == {"room-empty": {}}


def test_get_latest_values_for_rooms_empty_input_returns_empty_dict(db_session):
    assert get_latest_values_for_rooms(db_session, []) == {}


def test_get_latest_values_for_rooms_matches_the_single_room_function(db_session):
    _room(db_session, "room-a")
    _room(db_session, "room-b")
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            Reading(room_id="room-a", metric="temp_f", value=70.0, ts=now - timedelta(minutes=1)),
            Reading(room_id="room-a", metric="temp_f", value=71.0, ts=now),
            Reading(room_id="room-b", metric="co2_ppm", value=800.0, ts=now),
        ]
    )
    db_session.commit()

    batch = get_latest_values_for_rooms(db_session, ["room-a", "room-b"])
    assert batch["room-a"] == get_latest_values(db_session, "room-a")
    assert batch["room-b"] == get_latest_values(db_session, "room-b")
