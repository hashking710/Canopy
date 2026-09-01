from sqlalchemy import select

from canopy_agent.models import AlertEvent, AlertRule, Room
from canopy_agent.services.alerts import dispatch_alert_notifications, evaluate_alerts_for_room


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


def test_lt_condition_via_router(client, operator_id):
    client.post(
        "/api/alert-rules",
        json={
            "room_id": "greenhouse-a", "metric": "temp_f", "condition": "lt", "threshold": 60.0,
            "operator_id": operator_id,
        },
    )
    rules = client.get("/api/alert-rules?room_id=greenhouse-a").json()
    assert len(rules) == 1
    assert rules[0]["condition"] == "lt"


def test_create_alert_rule_requires_a_real_operator(client):
    resp = client.post(
        "/api/alert-rules",
        json={
            "room_id": "greenhouse-a", "metric": "temp_f", "condition": "gt", "threshold": 90.0,
            "operator_id": "op-does-not-exist",
        },
    )
    assert resp.status_code == 404


def test_create_alert_rule_rejects_viewer_role(client, operator_id):
    viewer = client.post("/api/operators", json={"name": "Just Looking", "role": "viewer"}).json()
    resp = client.post(
        "/api/alert-rules",
        json={
            "room_id": "greenhouse-a", "metric": "temp_f", "condition": "gt", "threshold": 90.0,
            "operator_id": viewer["id"],
        },
    )
    assert resp.status_code == 403


def test_delete_alert_rule(client, operator_id):
    created = client.post(
        "/api/alert-rules",
        json={
            "room_id": "greenhouse-a", "metric": "temp_f", "condition": "gt", "threshold": 90.0,
            "operator_id": operator_id,
        },
    ).json()
    deleted = client.request(
        "DELETE", f"/api/alert-rules/{created['id']}", params={"operator_id": operator_id}
    )
    assert deleted.status_code == 200
    assert client.get("/api/alert-rules").json() == []


def test_delete_alert_rule_rejects_viewer_role(client, operator_id):
    created = client.post(
        "/api/alert-rules",
        json={
            "room_id": "greenhouse-a", "metric": "temp_f", "condition": "gt", "threshold": 90.0,
            "operator_id": operator_id,
        },
    ).json()
    viewer = client.post("/api/operators", json={"name": "Just Looking", "role": "viewer"}).json()

    resp = client.request(
        "DELETE", f"/api/alert-rules/{created['id']}", params={"operator_id": viewer["id"]}
    )
    assert resp.status_code == 403


def test_acknowledge_alert_event_requires_valid_operator(client):
    unknown_operator = client.post("/api/alert-events/1/acknowledge", json={"operator_id": "not-real"})
    assert unknown_operator.status_code == 404


def test_acknowledge_alert_event_rejects_viewer_role(client, operator_id):
    viewer = client.post("/api/operators", json={"name": "Just Looking", "role": "viewer"}).json()
    resp = client.post("/api/alert-events/1/acknowledge", json={"operator_id": viewer["id"]})
    assert resp.status_code == 403


async def test_dispatch_alert_notifications_survives_personal_notify_failing(db_session, monkeypatch):
    """Regression test: dispatch_alert_notifications is called from the poller's
    main write path (poller.py's _write_room_reading) — an uncaught exception here
    would propagate up into poll_once()/poll_forever()'s exception handling same as
    any other poll-cycle failure, but a transient failure in the personal-
    notification path specifically must be swallowed at its own call site, same as
    a broken facility-wide channel already is (see the loop just above it in
    services/alerts.py)."""

    async def _boom(payload):
        raise RuntimeError("simulated transient DB failure")

    monkeypatch.setattr("canopy_agent.services.alerts.notify_operators_of_alert", _boom)

    room = make_room(db_session)
    db_session.add(AlertRule(id="rule-1", room_id=room.id, metric="temp_f", condition="gt", threshold=90.0))
    db_session.commit()
    opened = evaluate_alerts_for_room(db_session, room.id, {"temp_f": 95.0})
    db_session.commit()

    await dispatch_alert_notifications(opened, room.id)  # must not raise
