def make_room_body(**overrides):
    body = {
        "id": "test-room",
        "room_type": "greenhouse",
        "title": "Test Room",
        "section": "the greenhouse",
        "adapter_type": "mock",
        "metric_config": {"temp_f": {"label": "temp", "unit": "°F", "decimals": 1, "min": 65, "max": 85}},
    }
    body.update(overrides)
    return body


def test_mock_adapter_metric_config_without_min_max_is_rejected(client):
    resp = client.post(
        "/api/rooms", json=make_room_body(metric_config={"temp_f": {"label": "temp"}})
    )
    assert resp.status_code == 400
    assert "min" in resp.json()["detail"] or "max" in resp.json()["detail"]


def test_mock_adapter_derived_metric_does_not_need_min_max(client):
    resp = client.post(
        "/api/rooms", json=make_room_body(metric_config={"vpd_kpa": {"label": "VPD", "derived": "vpd"}})
    )
    assert resp.status_code == 200


def test_non_mock_adapter_does_not_require_min_max(client):
    resp = client.post(
        "/api/rooms",
        json=make_room_body(adapter_type="modbus", metric_config={"temp_f": {"label": "temp"}}),
    )
    # Should fail (if at all) for an unrelated reason, never the mock-specific min/max
    # rule, since this room isn't using the mock adapter.
    if resp.status_code == 400:
        assert "min" not in resp.json()["detail"] and "max" not in resp.json()["detail"]


def test_create_room(client):
    resp = client.post("/api/rooms", json=make_room_body())
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "test-room"
    assert body["room_type"] == "greenhouse"
    assert body["title"] == "Test Room"


def test_created_room_is_listed(client):
    client.post("/api/rooms", json=make_room_body())
    resp = client.get("/api/rooms")
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()]
    assert "test-room" in ids


def test_created_room_is_gettable_by_id(client):
    client.post("/api/rooms", json=make_room_body())
    resp = client.get("/api/rooms/test-room")
    assert resp.status_code == 200
    assert resp.json()["id"] == "test-room"


def test_room_config_endpoint_returns_editable_fields_not_in_the_list_payload(client):
    client.post("/api/rooms", json=make_room_body())

    listed = client.get("/api/rooms/test-room").json()
    assert "metric_config" not in listed  # RoomOut deliberately excludes this

    config = client.get("/api/rooms/test-room/config").json()
    assert config["adapter_type"] == "mock"
    assert config["metric_config"]["temp_f"]["label"] == "temp"
    assert config["adapter_config"] == {}


def test_room_config_for_nonexistent_room_is_404(client):
    resp = client.get("/api/rooms/does-not-exist/config")
    assert resp.status_code == 404


def test_cannot_create_a_room_with_a_duplicate_id(client):
    client.post("/api/rooms", json=make_room_body())
    resp = client.post("/api/rooms", json=make_room_body())
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]


def test_cannot_create_room_type_facility_via_this_endpoint(client):
    resp = client.post("/api/rooms", json=make_room_body(room_type="facility"))
    assert resp.status_code == 400
    assert "POST /api/facility" in resp.json()["detail"]


def test_room_id_must_match_the_safe_slug_pattern(client):
    resp = client.post("/api/rooms", json=make_room_body(id="Not A Valid Id!"))
    assert resp.status_code == 400
    assert "lowercase" in resp.json()["detail"]


def test_metric_config_without_a_label_is_rejected(client):
    resp = client.post("/api/rooms", json=make_room_body(metric_config={"temp_f": {"unit": "°F"}}))
    assert resp.status_code == 400
    assert "label" in resp.json()["detail"]


def test_unknown_adapter_type_is_rejected(client):
    resp = client.post("/api/rooms", json=make_room_body(adapter_type="totally_fake_adapter"))
    assert resp.status_code == 400
    assert "unknown adapter_type" in resp.json()["detail"]


def test_update_room(client):
    client.post("/api/rooms", json=make_room_body())
    resp = client.put("/api/rooms/test-room", json={"title": "Renamed Room", "badge": "Updated"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Renamed Room"
    assert body["badge"] == "Updated"


def test_update_room_only_touches_provided_fields(client):
    client.post("/api/rooms", json=make_room_body(subtitle="original subtitle"))
    resp = client.put("/api/rooms/test-room", json={"title": "New Title"})
    assert resp.status_code == 200
    assert resp.json()["subtitle"] == "original subtitle"


def test_update_nonexistent_room_is_404(client):
    resp = client.put("/api/rooms/nope", json={"title": "X"})
    assert resp.status_code == 404


def test_update_room_validates_metric_config(client):
    client.post("/api/rooms", json=make_room_body())
    resp = client.put("/api/rooms/test-room", json={"metric_config": {"bad": {}}})
    assert resp.status_code == 400


def test_delete_room(client):
    client.post("/api/rooms", json=make_room_body())
    resp = client.delete("/api/rooms/test-room")
    assert resp.status_code == 200
    assert resp.json() == {"id": "test-room", "deleted": True}

    assert client.get("/api/rooms/test-room").status_code == 404


def test_delete_nonexistent_room_is_404(client):
    resp = client.delete("/api/rooms/nope")
    assert resp.status_code == 404


def test_cannot_delete_the_facility_via_this_endpoint(client):
    client.post("/api/facility", json={})
    resp = client.delete("/api/rooms/facility")
    assert resp.status_code == 400


def test_deleting_a_room_also_removes_its_alert_rules(client):
    client.post("/api/rooms", json=make_room_body())
    rule_resp = client.post(
        "/api/alert-rules", json={"room_id": "test-room", "metric": "temp_f", "condition": "gt", "threshold": 90}
    )
    assert rule_resp.status_code == 200

    client.delete("/api/rooms/test-room")

    remaining = client.get("/api/alert-rules", params={"room_id": "test-room"}).json()
    assert remaining == []


def test_list_available_adapters_includes_mock(client):
    resp = client.get("/api/rooms/adapters/available")
    assert resp.status_code == 200
    adapter_types = [a["adapter_type"] for a in resp.json()]
    assert "mock" in adapter_types


def test_available_adapters_include_plugin_metadata(client):
    resp = client.get("/api/rooms/adapters/available")
    mock_entry = next(a for a in resp.json() if a["adapter_type"] == "mock")
    assert "plugin_name" in mock_entry
    assert "config_schema" in mock_entry
    assert "required_env_vars" in mock_entry
    assert mock_entry["required_env_vars"] == {}
    assert "default_metric_config" in mock_entry
    assert mock_entry["category"] == "testing"
    assert mock_entry["supports_discovery"] is False


def test_discover_rejects_unknown_adapter_type(client):
    resp = client.post("/api/rooms/adapters/not-a-real-adapter/discover")
    assert resp.status_code == 404


def test_discover_rejects_adapter_without_discovery_support(client):
    resp = client.post("/api/rooms/adapters/mock/discover")
    assert resp.status_code == 400
    assert "does not support device discovery" in resp.json()["detail"]
