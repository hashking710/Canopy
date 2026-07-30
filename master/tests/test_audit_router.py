from canopy_master.audit_store import record_relayed_event


def _seed(client, site_id: str, **overrides) -> None:
    payload = {
        "id": 1, "origin_device_id": "pi-veg", "entity_type": "plant", "entity_id": "plant-abc",
        "action": "moved", "actor": "Alex Rivera", "room_id": "greenhouse-a",
        "details": {}, "occurred_at": "2026-07-29T12:00:00+00:00", "entry_hash": "deadbeef",
    }
    payload.update(overrides)
    db = client.app.state.test_session_factory()
    try:
        record_relayed_event(db, site_id, payload)
    finally:
        db.close()


def test_empty_log_returns_empty_list(client):
    resp = client.get("/api/audit-log")
    assert resp.status_code == 200
    assert resp.json() == []


def test_lists_recorded_events(client):
    _seed(client, "site-1")

    resp = client.get("/api/audit-log")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["site_id"] == "site-1"
    assert body[0]["action"] == "moved"
    assert body[0]["actor"] == "Alex Rivera"


def test_filters_by_site_id(client):
    _seed(client, "site-1", id=1, entity_id="p1", entry_hash="h1")
    _seed(client, "site-2", id=1, entity_id="p2", entry_hash="h2")

    resp = client.get("/api/audit-log?site_id=site-1")
    body = resp.json()
    assert len(body) == 1
    assert body[0]["site_id"] == "site-1"
