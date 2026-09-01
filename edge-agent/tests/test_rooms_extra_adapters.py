def make_room_body(operator_id: str, **overrides):
    body = {
        "id": "multi-adapter-room",
        "room_type": "greenhouse",
        "title": "Multi Adapter Room",
        "adapter_type": "mock",
        "metric_config": {"temp_f": {"label": "temp", "unit": "°F", "decimals": 1, "min": 65, "max": 85}},
        "operator_id": operator_id,
    }
    body.update(overrides)
    return body


def test_add_extra_adapter(client, operator_id):
    client.post("/api/rooms", json=make_room_body(operator_id))
    resp = client.post(
        "/api/rooms/multi-adapter-room/adapters",
        json={"adapter_type": "mock", "adapter_config": {"note": "second sensor"}, "operator_id": operator_id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["adapter_type"] == "mock"
    assert body["adapter_config"] == {"note": "second sensor"}
    assert isinstance(body["id"], int)


def test_add_extra_adapter_requires_a_real_operator(client, operator_id):
    client.post("/api/rooms", json=make_room_body(operator_id))
    resp = client.post(
        "/api/rooms/multi-adapter-room/adapters",
        json={"adapter_type": "mock", "operator_id": "op-does-not-exist"},
    )
    assert resp.status_code == 404


def test_add_extra_adapter_rejects_viewer_role(client, operator_id):
    client.post("/api/rooms", json=make_room_body(operator_id))
    viewer = client.post("/api/operators", json={"name": "Just Looking", "role": "viewer"}).json()
    resp = client.post(
        "/api/rooms/multi-adapter-room/adapters", json={"adapter_type": "mock", "operator_id": viewer["id"]}
    )
    assert resp.status_code == 403


def test_added_extra_adapter_appears_in_room_config(client, operator_id):
    client.post("/api/rooms", json=make_room_body(operator_id))
    client.post("/api/rooms/multi-adapter-room/adapters", json={"adapter_type": "mock", "operator_id": operator_id})

    resp = client.get("/api/rooms/multi-adapter-room/config")
    assert resp.status_code == 200
    extras = resp.json()["extra_adapters"]
    assert len(extras) == 1
    assert extras[0]["adapter_type"] == "mock"


def test_add_extra_adapter_unknown_type_rejected(client, operator_id):
    client.post("/api/rooms", json=make_room_body(operator_id))
    resp = client.post(
        "/api/rooms/multi-adapter-room/adapters",
        json={"adapter_type": "totally-bogus-adapter", "operator_id": operator_id},
    )
    assert resp.status_code == 400
    assert "totally-bogus-adapter" in resp.json()["detail"]


def test_add_extra_adapter_room_not_found(client, operator_id):
    resp = client.post(
        "/api/rooms/no-such-room/adapters", json={"adapter_type": "mock", "operator_id": operator_id}
    )
    assert resp.status_code == 404


def test_remove_extra_adapter(client, operator_id):
    client.post("/api/rooms", json=make_room_body(operator_id))
    add_resp = client.post(
        "/api/rooms/multi-adapter-room/adapters", json={"adapter_type": "mock", "operator_id": operator_id}
    )
    adapter_id = add_resp.json()["id"]

    del_resp = client.request(
        "DELETE", f"/api/rooms/multi-adapter-room/adapters/{adapter_id}", params={"operator_id": operator_id}
    )
    assert del_resp.status_code == 200
    assert del_resp.json() == {"id": adapter_id, "deleted": True}

    config = client.get("/api/rooms/multi-adapter-room/config").json()
    assert config["extra_adapters"] == []


def test_remove_extra_adapter_requires_a_real_operator(client, operator_id):
    client.post("/api/rooms", json=make_room_body(operator_id))
    add_resp = client.post(
        "/api/rooms/multi-adapter-room/adapters", json={"adapter_type": "mock", "operator_id": operator_id}
    )
    adapter_id = add_resp.json()["id"]

    resp = client.request(
        "DELETE",
        f"/api/rooms/multi-adapter-room/adapters/{adapter_id}",
        params={"operator_id": "op-does-not-exist"},
    )
    assert resp.status_code == 404


def test_remove_extra_adapter_not_found(client, operator_id):
    client.post("/api/rooms", json=make_room_body(operator_id))
    resp = client.request(
        "DELETE", "/api/rooms/multi-adapter-room/adapters/999999", params={"operator_id": operator_id}
    )
    assert resp.status_code == 404


def test_remove_extra_adapter_wrong_room_rejected(client, operator_id):
    """An adapter id that's real but belongs to a *different* room must not be
    deletable through this room's URL — otherwise room_id in the path is decorative."""
    client.post("/api/rooms", json=make_room_body(operator_id))
    client.post("/api/rooms", json=make_room_body(operator_id, id="other-room"))
    add_resp = client.post(
        "/api/rooms/multi-adapter-room/adapters", json={"adapter_type": "mock", "operator_id": operator_id}
    )
    adapter_id = add_resp.json()["id"]

    resp = client.request(
        "DELETE", f"/api/rooms/other-room/adapters/{adapter_id}", params={"operator_id": operator_id}
    )
    assert resp.status_code == 404


def test_deleting_room_cleans_up_its_extra_adapters(client, operator_id):
    client.post("/api/rooms", json=make_room_body(operator_id))
    client.post("/api/rooms/multi-adapter-room/adapters", json={"adapter_type": "mock", "operator_id": operator_id})

    resp = client.request(
        "DELETE", "/api/rooms/multi-adapter-room", params={"operator_id": operator_id}
    )
    assert resp.status_code == 200

    # Re-creating the same room id afterward must not resurface the old room's
    # extra adapters — the real proof cleanup happened, not just that the room
    # itself is gone.
    client.post("/api/rooms", json=make_room_body(operator_id))
    config = client.get("/api/rooms/multi-adapter-room/config").json()
    assert config["extra_adapters"] == []
