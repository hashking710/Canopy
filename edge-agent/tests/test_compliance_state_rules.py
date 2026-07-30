def test_state_rules_endpoint_defaults_to_california(client):
    resp = client.get("/api/compliance/state-rules")
    assert resp.status_code == 200
    body = resp.json()
    assert body["active"]["state_code"] == "CA"
    assert body["active"]["deadline_confidence"] == "primary_source"
    assert body["active"]["home_grow"]["recreational_limit"]["count"] == 6
    assert body["explicitly_set"] is False
    codes = {s["state_code"] for s in body["available"]}
    assert {"CA", "CO", "OK", "MI", "AZ", "IL", "MD", "MA", "MO", "NV", "OH"}.issubset(codes)


def test_setting_active_state_changes_get_and_marks_explicitly_set(client, operator_id):
    resp = client.post("/api/compliance/state-rules", json={"state_code": "CO", "operator_id": operator_id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["active"]["state_code"] == "CO"
    assert body["explicitly_set"] is True

    # Persists — a later GET reflects the operator's choice, not the CA default.
    resp = client.get("/api/compliance/state-rules")
    body = resp.json()
    assert body["active"]["state_code"] == "CO"
    assert body["explicitly_set"] is True


def test_setting_active_state_accepts_lowercase_and_normalizes(client, operator_id):
    resp = client.post("/api/compliance/state-rules", json={"state_code": "co", "operator_id": operator_id})
    assert resp.status_code == 200
    assert resp.json()["active"]["state_code"] == "CO"


def test_setting_unknown_state_rejected(client, operator_id):
    resp = client.post("/api/compliance/state-rules", json={"state_code": "ZZ", "operator_id": operator_id})
    assert resp.status_code == 400
    assert "ZZ" in resp.json()["detail"]

    # Rejected — the active state must not have changed.
    resp = client.get("/api/compliance/state-rules")
    assert resp.json()["active"]["state_code"] == "CA"
    assert resp.json()["explicitly_set"] is False


def test_setting_active_state_requires_a_real_operator(client):
    resp = client.post("/api/compliance/state-rules", json={"state_code": "CO", "operator_id": "no-such-operator"})
    assert resp.status_code == 404


def test_setting_active_state_writes_an_audit_entry(client, operator_id):
    client.post("/api/compliance/state-rules", json={"state_code": "CO", "operator_id": operator_id})
    entries = client.get("/api/compliance/audit-log?entity_type=facility").json()
    assert any(
        e["action"] == "compliance_state_changed" and e["details"] == {"from": "CA", "to": "CO"} for e in entries
    )


def test_setting_active_state_changes_reconciliation_cadence_used(client, operator_id):
    # California requires review at least every 30 days (Cal. Code Regs. tit. 4,
    # §15051(a)(1)); Colorado requires daily reconciliation (1) — the reconciliation
    # endpoint must pick up this real behavioral difference from the *active* state,
    # not a hardcoded default, once an operator switches it.
    ca_cadence = client.get("/api/compliance/state-rules").json()["active"]["reconciliation_cadence_days"]
    assert ca_cadence == 30

    client.post("/api/compliance/state-rules", json={"state_code": "CO", "operator_id": operator_id})
    co_cadence = client.get("/api/compliance/state-rules").json()["active"]["reconciliation_cadence_days"]
    assert co_cadence == 1

    # And the reconciliation endpoint itself still works with the new state active.
    client.post(
        "/api/compliance/plant-batches",
        json={
            "name": "CADENCE-TEST-001",
            "batch_type": "Clone",
            "strain": "Test Strain",
            "room_id": "test-room",
            "planted_date": "2026-07-01",
            "count": 5,
            "operator_id": operator_id,
        },
    )
    recon = client.get("/api/compliance/reconciliation").json()
    assert any(r["room_id"] == "test-room" for r in recon)


def test_reconciliation_response_includes_stale_field(client, operator_id):
    client.post(
        "/api/compliance/plant-batches",
        json={
            "name": "STALE-TEST-001",
            "batch_type": "Clone",
            "strain": "Test Strain",
            "room_id": "test-room",
            "planted_date": "2026-07-01",
            "count": 5,
            "operator_id": operator_id,
        },
    )
    recon = client.get("/api/compliance/reconciliation").json()
    row = next(r for r in recon if r["room_id"] == "test-room")
    assert "stale" in row
    # A room that's simply never been physically counted shouldn't be reported "stale"
    # regardless of the active state's cadence — it's "needs first count" instead, a
    # separate condition already covered by needs_recount (see is_recount_stale, only
    # evaluated once a last_count actually exists).
    assert row["stale"] is False
