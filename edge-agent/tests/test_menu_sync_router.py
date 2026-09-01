def test_status_defaults_to_null_provider(client):
    resp = client.get("/api/menu-sync/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_provider"] == "null"
    assert body["last_synced_at"] is None
    assert any(p["type"] == "null" for p in body["available_providers"])


def test_run_now_updates_status(client, operator_id):
    run_resp = client.post("/api/menu-sync/run", params={"operator_id": operator_id})
    assert run_resp.status_code == 200
    assert run_resp.json() == {"pushed": 0, "skipped": 0}  # null provider, nothing to push either way

    status = client.get("/api/menu-sync/status").json()
    assert status["last_synced_at"] is not None
    assert status["last_result"] == {"pushed": 0, "skipped": 0}
    assert status["last_error"] is None


def test_run_now_requires_a_real_operator(client):
    resp = client.post("/api/menu-sync/run", params={"operator_id": "op-does-not-exist"})
    assert resp.status_code == 404


def test_run_now_rejects_viewer_role(client, operator_id):
    viewer = client.post("/api/operators", json={"name": "Just Looking", "role": "viewer"}).json()
    resp = client.post("/api/menu-sync/run", params={"operator_id": viewer["id"]})
    assert resp.status_code == 403
