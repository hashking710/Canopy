def make_room_body(**overrides):
    body = {
        "id": "multi-adapter-room",
        "room_type": "greenhouse",
        "title": "Multi Adapter Room",
        "adapter_type": "mock",
        "metric_config": {"temp_f": {"label": "temp", "unit": "°F", "decimals": 1, "min": 65, "max": 85}},
    }
    body.update(overrides)
    return body


def test_add_extra_adapter(client):
    client.post("/api/rooms", json=make_room_body())
    resp = client.post(
        "/api/rooms/multi-adapter-room/adapters",
        json={"adapter_type": "mock", "adapter_config": {"note": "second sensor"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["adapter_type"] == "mock"
    assert body["adapter_config"] == {"note": "second sensor"}
    assert isinstance(body["id"], int)


def test_added_extra_adapter_appears_in_room_config(client):
    client.post("/api/rooms", json=make_room_body())
    client.post("/api/rooms/multi-adapter-room/adapters", json={"adapter_type": "mock"})

    resp = client.get("/api/rooms/multi-adapter-room/config")
    assert resp.status_code == 200
    extras = resp.json()["extra_adapters"]
    assert len(extras) == 1
    assert extras[0]["adapter_type"] == "mock"


def test_add_extra_adapter_unknown_type_rejected(client):
    client.post("/api/rooms", json=make_room_body())
    resp = client.post(
        "/api/rooms/multi-adapter-room/adapters",
        json={"adapter_type": "totally-bogus-adapter"},
    )
    assert resp.status_code == 400
    assert "totally-bogus-adapter" in resp.json()["detail"]


def test_add_extra_adapter_room_not_found(client):
    resp = client.post("/api/rooms/no-such-room/adapters", json={"adapter_type": "mock"})
    assert resp.status_code == 404


def test_remove_extra_adapter(client):
    client.post("/api/rooms", json=make_room_body())
    add_resp = client.post("/api/rooms/multi-adapter-room/adapters", json={"adapter_type": "mock"})
    adapter_id = add_resp.json()["id"]

    del_resp = client.delete(f"/api/rooms/multi-adapter-room/adapters/{adapter_id}")
    assert del_resp.status_code == 200
    assert del_resp.json() == {"id": adapter_id, "deleted": True}

    config = client.get("/api/rooms/multi-adapter-room/config").json()
    assert config["extra_adapters"] == []


def test_remove_extra_adapter_not_found(client):
    client.post("/api/rooms", json=make_room_body())
    resp = client.delete("/api/rooms/multi-adapter-room/adapters/999999")
    assert resp.status_code == 404


def test_remove_extra_adapter_wrong_room_rejected(client):
    """An adapter id that's real but belongs to a *different* room must not be
    deletable through this room's URL — otherwise room_id in the path is decorative."""
    client.post("/api/rooms", json=make_room_body())
    client.post("/api/rooms", json=make_room_body(id="other-room"))
    add_resp = client.post("/api/rooms/multi-adapter-room/adapters", json={"adapter_type": "mock"})
    adapter_id = add_resp.json()["id"]

    resp = client.delete(f"/api/rooms/other-room/adapters/{adapter_id}")
    assert resp.status_code == 404


def test_deleting_room_cleans_up_its_extra_adapters(client):
    client.post("/api/rooms", json=make_room_body())
    client.post("/api/rooms/multi-adapter-room/adapters", json={"adapter_type": "mock"})

    resp = client.delete("/api/rooms/multi-adapter-room")
    assert resp.status_code == 200

    # Re-creating the same room id afterward must not resurface the old room's
    # extra adapters — the real proof cleanup happened, not just that the room
    # itself is gone.
    client.post("/api/rooms", json=make_room_body())
    config = client.get("/api/rooms/multi-adapter-room/config").json()
    assert config["extra_adapters"] == []
