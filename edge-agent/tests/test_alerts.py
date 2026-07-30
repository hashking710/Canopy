from sqlalchemy import select

from canopy_agent.models import AlertEvent, AlertRule, Room
from canopy_agent.services.alerts import evaluate_alerts_for_room


def make_room(db_session, room_id="greenhouse-a"):
    room = Room(id=room_id, room_type="greenhouse", path=f"~/{room_id}", metric_config={})
    db_session.add(room)
    db_session.commit()
    return room


def test_breach_opens_a_new_alert_event(db_session):
    make_room(db_session)
    db_session.add(AlertRule(id="rule-1", room_id="greenhouse-a", metric="temp_f", condition="gt", threshold=90.0))
    db_session.commit()

    opened = evaluate_alerts_for_room(db_session, "greenhouse-a", {"temp_f": 95.0})
    db_session.commit()

    assert len(opened) == 1
    assert opened[0].value == 95.0
    open_events = db_session.execute(select(AlertEvent).where(AlertEvent.resolved_at.is_(None))).scalars().all()
    assert len(open_events) == 1


def test_repeated_breach_does_not_open_duplicate_events(db_session):
    make_room(db_session)
    db_session.add(AlertRule(id="rule-1", room_id="greenhouse-a", metric="temp_f", condition="gt", threshold=90.0))
    db_session.commit()

    evaluate_alerts_for_room(db_session, "greenhouse-a", {"temp_f": 95.0})
    db_session.commit()
    second_cycle = evaluate_alerts_for_room(db_session, "greenhouse-a", {"temp_f": 96.0})
    db_session.commit()

    assert second_cycle == []
    all_events = db_session.execute(select(AlertEvent)).scalars().all()
    assert len(all_events) == 1


def test_reading_back_in_range_resolves_the_event(db_session):
    make_room(db_session)
    db_session.add(AlertRule(id="rule-1", room_id="greenhouse-a", metric="temp_f", condition="gt", threshold=90.0))
    db_session.commit()

    evaluate_alerts_for_room(db_session, "greenhouse-a", {"temp_f": 95.0})
    db_session.commit()
    evaluate_alerts_for_room(db_session, "greenhouse-a", {"temp_f": 80.0})
    db_session.commit()

    event = db_session.execute(select(AlertEvent)).scalar_one()
    assert event.resolved_at is not None


def test_disabled_rule_is_not_evaluated(db_session):
    make_room(db_session)
    db_session.add(
        AlertRule(id="rule-1", room_id="greenhouse-a", metric="temp_f", condition="gt", threshold=90.0, enabled=False)
    )
    db_session.commit()

    opened = evaluate_alerts_for_room(db_session, "greenhouse-a", {"temp_f": 999.0})
    assert opened == []


def test_lt_condition_via_router(client):
    client.post(
        "/api/alert-rules", json={"room_id": "greenhouse-a", "metric": "temp_f", "condition": "lt", "threshold": 60.0}
    )
    rules = client.get("/api/alert-rules?room_id=greenhouse-a").json()
    assert len(rules) == 1
    assert rules[0]["condition"] == "lt"


def test_delete_alert_rule(client):
    created = client.post(
        "/api/alert-rules", json={"room_id": "greenhouse-a", "metric": "temp_f", "condition": "gt", "threshold": 90.0}
    ).json()
    deleted = client.delete(f"/api/alert-rules/{created['id']}")
    assert deleted.status_code == 200
    assert client.get("/api/alert-rules").json() == []


def test_acknowledge_alert_event_requires_valid_operator(client):
    unknown_operator = client.post("/api/alert-events/1/acknowledge", json={"operator_id": "not-real"})
    assert unknown_operator.status_code == 404
