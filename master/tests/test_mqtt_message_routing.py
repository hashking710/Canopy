import json
from types import SimpleNamespace

from canopy_master import mqtt_subscriber
from canopy_master.audit_store import list_relayed_events
from canopy_master.store import Store


def _fake_message(topic: str, payload: dict) -> SimpleNamespace:
    return SimpleNamespace(topic=topic, payload=json.dumps(payload).encode())


async def test_state_message_upserts_the_store(monkeypatch):
    fresh_store = Store()
    monkeypatch.setattr(mqtt_subscriber, "store", fresh_store)
    message = _fake_message("canopy/site-1/greenhouse-a/state", {"id": "greenhouse-a", "stats": []})

    await mqtt_subscriber._handle_state_message(message, "canopy/site-1/greenhouse-a/state".split("/"))

    assert fresh_store.rooms_for_site("site-1") == [{"id": "greenhouse-a", "stats": []}]


def test_audit_message_persists_via_a_fresh_session(monkeypatch, db_session):
    monkeypatch.setattr(mqtt_subscriber, "SessionLocal", lambda: db_session)
    # record_relayed_event commits internally — patch db_session.close to a no-op so
    # the fixture's own session (reused for the assertion below) stays usable.
    monkeypatch.setattr(db_session, "close", lambda: None)

    payload = {
        "id": 1, "origin_device_id": "pi-veg", "entity_type": "plant", "entity_id": "plant-abc",
        "action": "moved", "actor": "Alex Rivera", "room_id": "greenhouse-a",
        "details": {}, "occurred_at": "2026-07-29T12:00:00+00:00", "entry_hash": "deadbeef",
    }
    message = _fake_message("canopy/site-1/audit-events", payload)

    mqtt_subscriber._handle_audit_message(message, "canopy/site-1/audit-events".split("/"))

    events = list_relayed_events(db_session)
    assert len(events) == 1
    assert events[0].site_id == "site-1"
    assert events[0].actor == "Alex Rivera"


def test_audit_message_with_malformed_json_is_ignored_not_raised(monkeypatch, db_session):
    monkeypatch.setattr(mqtt_subscriber, "SessionLocal", lambda: db_session)
    message = SimpleNamespace(topic="canopy/site-1/audit-events", payload=b"not json")

    mqtt_subscriber._handle_audit_message(message, "canopy/site-1/audit-events".split("/"))  # must not raise

    assert list_relayed_events(db_session) == []
