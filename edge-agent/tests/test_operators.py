def test_create_and_list_operators(client):
    created = client.post("/api/operators", json={"name": "Sam Grower"}).json()
    assert created["has_pin"] is False

    listing = client.get("/api/operators").json()
    assert any(o["id"] == created["id"] and o["name"] == "Sam Grower" for o in listing)


def test_duplicate_operator_name_rejected(client):
    client.post("/api/operators", json={"name": "Dup Operator"})
    dup = client.post("/api/operators", json={"name": "Dup Operator"})
    assert dup.status_code == 400


def test_pin_verification(client):
    created = client.post("/api/operators", json={"name": "PIN Operator", "pin": "9999"}).json()
    assert created["has_pin"] is True

    correct = client.post(f"/api/operators/{created['id']}/verify-pin", json={"pin": "9999"}).json()
    assert correct["valid"] is True

    wrong = client.post(f"/api/operators/{created['id']}/verify-pin", json={"pin": "0000"}).json()
    assert wrong["valid"] is False


def test_reset_pin(client):
    created = client.post("/api/operators", json={"name": "Reset Me", "pin": "1111"}).json()

    reset = client.post(f"/api/operators/{created['id']}/reset-pin", json={"pin": "2222"}).json()
    assert reset["has_pin"] is True
    old_pin_rejected = client.post(f"/api/operators/{created['id']}/verify-pin", json={"pin": "1111"}).json()
    assert old_pin_rejected["valid"] is False
    new_pin_accepted = client.post(f"/api/operators/{created['id']}/verify-pin", json={"pin": "2222"}).json()
    assert new_pin_accepted["valid"] is True

    cleared = client.post(f"/api/operators/{created['id']}/reset-pin", json={}).json()
    assert cleared["has_pin"] is False


def test_pin_policy_defaults_to_not_required(client):
    policy = client.get("/api/operators/pin-policy").json()
    assert policy["require_operator_pins"] is False


def test_enabling_pin_policy_blocks_creating_a_pinless_operator(client):
    admin = client.post("/api/operators", json={"name": "Policy Admin", "pin": "1234"}).json()

    client.post("/api/operators/pin-policy", json={"require_operator_pins": True, "operator_id": admin["id"]})

    rejected = client.post("/api/operators", json={"name": "No Pin Operator"})
    assert rejected.status_code == 400

    accepted = client.post("/api/operators", json={"name": "Has A Pin", "pin": "5555"})
    assert accepted.status_code == 200


def test_enabling_pin_policy_blocks_clearing_an_existing_pin(client):
    admin = client.post("/api/operators", json={"name": "Policy Admin 2", "pin": "1234"}).json()
    client.post("/api/operators/pin-policy", json={"require_operator_pins": True, "operator_id": admin["id"]})

    cleared = client.post(f"/api/operators/{admin['id']}/reset-pin", json={})
    assert cleared.status_code == 400

    still_settable = client.post(f"/api/operators/{admin['id']}/reset-pin", json={"pin": "4321"})
    assert still_settable.status_code == 200


def test_pin_policy_reports_how_many_active_operators_still_lack_one(client):
    admin = client.post("/api/operators", json={"name": "Policy Admin 3", "pin": "1234"}).json()
    client.post("/api/operators", json={"name": "Pinless One"})
    client.post("/api/operators", json={"name": "Pinless Two"})

    policy = client.get("/api/operators/pin-policy").json()
    assert policy["operators_without_pin"] >= 2  # at least the two just created

    client.post("/api/operators/pin-policy", json={"require_operator_pins": True, "operator_id": admin["id"]})
    policy_after = client.get("/api/operators/pin-policy").json()
    assert policy_after["require_operator_pins"] is True
    # turning the policy on doesn't retroactively force-remove pinless operators —
    # it only stops new ones/clearing, so the count is unchanged
    assert policy_after["operators_without_pin"] == policy["operators_without_pin"]


def test_pin_policy_change_is_audit_logged(client):
    admin = client.post("/api/operators", json={"name": "Policy Admin 4", "pin": "1234"}).json()
    client.post("/api/operators/pin-policy", json={"require_operator_pins": True, "operator_id": admin["id"]})

    log = client.get("/api/compliance/audit-log").json()
    entry = next(e for e in log if e["action"] == "pin_policy_changed")
    assert entry["actor"] == "Policy Admin 4"
    assert entry["details"]["to"] is True


def test_deactivate_operator_disappears_from_active_list(client):
    created = client.post("/api/operators", json={"name": "Leaving Soon"}).json()
    assert any(o["id"] == created["id"] for o in client.get("/api/operators").json())

    deactivated = client.post(f"/api/operators/{created['id']}/deactivate").json()
    assert deactivated["active"] is False
    assert not any(o["id"] == created["id"] for o in client.get("/api/operators").json())

    # deactivated operators can no longer authenticate compliance actions
    verify = client.post(f"/api/operators/{created['id']}/verify-pin", json={"pin": "anything"})
    assert verify.status_code == 404
