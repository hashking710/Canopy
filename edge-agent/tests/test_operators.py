def test_create_and_list_operators(client):
    created = client.post("/api/operators", json={"name": "Sam Grower"}).json()
    assert created["has_pin"] is False

    listing = client.get("/api/operators").json()
    assert any(o["id"] == created["id"] and o["name"] == "Sam Grower" for o in listing)


# ---- roles ----------------------------------------------------------------------------


def test_the_very_first_operator_is_always_admin_regardless_of_requested_role(client):
    """A brand-new facility has no operators at all yet, and set_operator_role
    itself requires an existing admin to grant anyone else the admin role — so
    without this, a fresh install would have no path to ever getting one."""
    first = client.post("/api/operators", json={"name": "First Ever", "role": "viewer"}).json()
    assert first["role"] == "admin"


def test_the_second_operator_gets_the_requested_role_normally(client):
    client.post("/api/operators", json={"name": "First Ever"})  # becomes admin
    second = client.post("/api/operators", json={"name": "Second One", "role": "viewer"}).json()
    assert second["role"] == "viewer"


def test_create_operator_defaults_to_operator_role(client):
    client.post("/api/operators", json={"name": "First Ever"})  # becomes admin
    second = client.post("/api/operators", json={"name": "No Role Specified"}).json()
    assert second["role"] == "operator"


def test_create_operator_rejects_an_unknown_role(client):
    resp = client.post("/api/operators", json={"name": "Bad Role", "role": "superuser"})
    assert resp.status_code == 400


def test_set_operator_role_rejects_an_unknown_role(client, operator_id):
    target = client.post("/api/operators", json={"name": "Target"}).json()
    resp = client.post(
        f"/api/operators/{target['id']}/role", json={"role": "superuser", "acting_operator_id": operator_id}
    )
    assert resp.status_code == 400


def test_set_operator_role_rejects_an_unknown_acting_operator(client, operator_id):
    target = client.post("/api/operators", json={"name": "Target"}).json()
    resp = client.post(
        f"/api/operators/{target['id']}/role", json={"role": "admin", "acting_operator_id": "op-nope"}
    )
    assert resp.status_code == 404


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


# ---- notification preferences ----------------------------------------------------------


def test_create_operator_accepts_notification_preferences(client):
    created = client.post(
        "/api/operators",
        json={
            "name": "Manager Mia", "notify_email": "mia@example.com", "notify_on_alerts": True,
            "notify_on_system_errors": True, "notify_min_severity": "warning",
        },
    ).json()
    assert created["notify_email"] == "mia@example.com"
    assert created["notify_on_alerts"] is True
    assert created["notify_min_severity"] == "warning"


def test_create_operator_defaults_notifications_off(client):
    created = client.post("/api/operators", json={"name": "No Prefs"}).json()
    assert created["notify_email"] is None
    assert created["notify_on_alerts"] is False
    assert created["notify_on_system_errors"] is False
    assert created["notify_min_severity"] == "critical"


def test_create_operator_rejects_unknown_severity(client):
    resp = client.post("/api/operators", json={"name": "Bad Severity", "notify_min_severity": "urgent"})
    assert resp.status_code == 400


def test_update_notification_preferences(client):
    created = client.post("/api/operators", json={"name": "Grower Greg"}).json()
    resp = client.put(
        f"/api/operators/{created['id']}/notification-preferences",
        json={
            "notify_email": "greg@example.com", "notify_on_alerts": True,
            "notify_on_system_errors": False, "notify_min_severity": "warning",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["notify_email"] == "greg@example.com"
    assert body["notify_on_alerts"] is True
    assert body["notify_min_severity"] == "warning"

    # persisted, not just echoed back
    listed = next(o for o in client.get("/api/operators").json() if o["id"] == created["id"])
    assert listed["notify_email"] == "greg@example.com"


def test_update_notification_preferences_for_nonexistent_operator_is_404(client):
    resp = client.put(
        "/api/operators/does-not-exist/notification-preferences",
        json={"notify_on_alerts": True},
    )
    assert resp.status_code == 404


def test_update_notification_preferences_rejects_unknown_severity(client):
    created = client.post("/api/operators", json={"name": "Grower Greg"}).json()
    resp = client.put(
        f"/api/operators/{created['id']}/notification-preferences",
        json={"notify_min_severity": "urgent"},
    )
    assert resp.status_code == 400


def test_update_notification_preferences_has_no_role_gate_self_service(client):
    """Deliberately not role-gated — this is personal preference data about the
    operator making the request, same "self-service" reasoning as PIN reset."""
    viewer = client.post("/api/operators", json={"name": "Just Looking", "role": "viewer"}).json()
    resp = client.put(
        f"/api/operators/{viewer['id']}/notification-preferences",
        json={"notify_on_alerts": True},
    )
    assert resp.status_code == 200
