import os

import pytest

# A real key from an installed plugin — required_env_vars is aggregated from
# whatever's actually installed (adapters/registry.py), so this only works because
# canopy-adapter-govee is installed in this test environment, same as every other
# plugin-dependent test in this suite.
REAL_KEY = "CANOPY_GOVEE_API_KEY"


@pytest.fixture(autouse=True)
def _clean_environ():
    """set_secret/clear_secret mutate the real process os.environ directly (that's
    the whole point — see routers/secrets.py), which plain pytest monkeypatch can't
    auto-revert since it bypasses monkeypatch's own setenv. Belt-and-suspenders
    cleanup around every test in this file."""
    previous = os.environ.get(REAL_KEY)
    yield
    if previous is None:
        os.environ.pop(REAL_KEY, None)
    else:
        os.environ[REAL_KEY] = previous


def test_list_secrets_includes_a_real_known_key(client):
    resp = client.get("/api/secrets")
    assert resp.status_code == 200
    keys = {s["key"] for s in resp.json()}
    assert REAL_KEY in keys


def test_list_secrets_never_returns_the_value(client):
    resp = client.get("/api/secrets")
    for entry in resp.json():
        assert "value" not in entry


def test_list_secrets_includes_which_plugin_needs_each_key(client):
    """Lets the dashboard group a long, flat credential list by vendor instead of
    one undifferentiated alphabetical wall of rows — see Settings.tsx's
    CredentialsCard."""
    resp = client.get("/api/secrets")
    entry = next(s for s in resp.json() if s["key"] == REAL_KEY)
    assert entry["plugin_name"] == "Govee (Cloud API)"


def test_list_secrets_is_sorted_by_plugin_then_key(client):
    entries = client.get("/api/secrets").json()
    sort_keys = [(e["plugin_name"], e["key"]) for e in entries]
    assert sort_keys == sorted(sort_keys)


def test_unset_secret_reports_not_set(client):
    os.environ.pop(REAL_KEY, None)
    resp = client.get("/api/secrets")
    entry = next(s for s in resp.json() if s["key"] == REAL_KEY)
    assert entry["is_set"] is False
    assert entry["set_via_dashboard"] is False


def test_set_secret_takes_effect_immediately(client, operator_id):
    # operator_id is the first operator ever created in this test's fresh DB —
    # see routers/operators.py's create_operator — so it's already role="admin",
    # exactly the bootstrapping case that makes this work at all on a brand-new
    # facility with no operators registered yet.
    resp = client.put(f"/api/secrets/{REAL_KEY}", json={"value": "test-api-key", "operator_id": operator_id})
    assert resp.status_code == 200
    assert resp.json() == {"key": REAL_KEY, "is_set": True}

    # Takes effect on this process's real os.environ right away — not just in the DB.
    assert os.environ.get(REAL_KEY) == "test-api-key"

    listed = client.get("/api/secrets").json()
    entry = next(s for s in listed if s["key"] == REAL_KEY)
    assert entry["is_set"] is True
    assert entry["set_via_dashboard"] is True


def test_bootstrap_replays_stored_secrets_into_environ(db_session):
    """Unit-tests services/secrets_bootstrap.py directly: a FacilitySecret row
    written on one process (e.g. before a restart) must come back as a real
    os.environ value the next time this runs — this is what main.py's lifespan
    calls before the poller or any adapter is constructed."""
    from canopy_agent.models import FacilitySecret
    from canopy_agent.services.secrets_bootstrap import load_secrets_into_environ

    os.environ.pop(REAL_KEY, None)
    db_session.add(FacilitySecret(key=REAL_KEY, value="restored-from-db"))
    db_session.commit()

    load_secrets_into_environ(db_session)

    assert os.environ.get(REAL_KEY) == "restored-from-db"


def test_bootstrap_overrides_whatever_was_already_in_environ(db_session, monkeypatch):
    """A DB-stored value (someone explicitly set this via the dashboard) must win
    over whatever docker-compose.yml/.env already put in the environment — that's
    the documented precedence in FacilitySecret's own docstring."""
    from canopy_agent.models import FacilitySecret
    from canopy_agent.services.secrets_bootstrap import load_secrets_into_environ

    monkeypatch.setenv(REAL_KEY, "from-compose")
    db_session.add(FacilitySecret(key=REAL_KEY, value="from-dashboard"))
    db_session.commit()

    load_secrets_into_environ(db_session)

    assert os.environ.get(REAL_KEY) == "from-dashboard"


def test_clear_secret_removes_it(client, operator_id):
    client.put(f"/api/secrets/{REAL_KEY}", json={"value": "temp-key", "operator_id": operator_id})
    resp = client.request("DELETE", f"/api/secrets/{REAL_KEY}", json={"operator_id": operator_id})
    assert resp.status_code == 200
    assert resp.json() == {"key": REAL_KEY, "is_set": False}
    assert os.environ.get(REAL_KEY) is None

    listed = client.get("/api/secrets").json()
    entry = next(s for s in listed if s["key"] == REAL_KEY)
    assert entry["is_set"] is False


def test_set_unknown_key_rejected(client, operator_id):
    resp = client.put("/api/secrets/NOT_A_REAL_ENV_VAR", json={"value": "x", "operator_id": operator_id})
    assert resp.status_code == 400
    assert "unknown secret key" in resp.json()["detail"]


def test_set_empty_value_rejected(client, operator_id):
    resp = client.put(f"/api/secrets/{REAL_KEY}", json={"value": "   ", "operator_id": operator_id})
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"]


def test_clear_unknown_key_rejected(client, operator_id):
    resp = client.request("DELETE", "/api/secrets/NOT_A_REAL_ENV_VAR", json={"operator_id": operator_id})
    assert resp.status_code == 400


# ---- role gating — the actual new behavior, not just "existing tests still pass
# once an operator_id is supplied" ---------------------------------------------------


def test_set_secret_requires_a_real_operator(client):
    resp = client.put(f"/api/secrets/{REAL_KEY}", json={"value": "x", "operator_id": "op-does-not-exist"})
    assert resp.status_code == 404


def test_set_secret_rejects_operator_role(client, operator_id):
    # The fixture's operator is auto-admin (first ever) — register a second,
    # ordinary operator (defaults to role="operator") to prove the *role* itself
    # is what's being checked, not just "any real operator_id works".
    second = client.post("/api/operators", json={"name": "Regular Operator"}).json()
    assert second["role"] == "operator"

    resp = client.put(f"/api/secrets/{REAL_KEY}", json={"value": "x", "operator_id": second["id"]})
    assert resp.status_code == 403
    assert "operator" in resp.json()["detail"]


def test_set_secret_rejects_viewer_role(client, operator_id):
    viewer = client.post("/api/operators", json={"name": "Viewer Only", "role": "viewer"}).json()
    assert viewer["role"] == "viewer"

    resp = client.put(f"/api/secrets/{REAL_KEY}", json={"value": "x", "operator_id": viewer["id"]})
    assert resp.status_code == 403


def test_admin_can_promote_another_operator_to_admin(client, operator_id):
    second = client.post("/api/operators", json={"name": "Future Admin"}).json()
    assert second["role"] == "operator"

    resp = client.post(
        f"/api/operators/{second['id']}/role", json={"role": "admin", "acting_operator_id": operator_id}
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"

    # Now actually usable for an admin-gated action.
    set_resp = client.put(f"/api/secrets/{REAL_KEY}", json={"value": "x", "operator_id": second["id"]})
    assert set_resp.status_code == 200


def test_non_admin_cannot_promote_anyone(client, operator_id):
    non_admin = client.post("/api/operators", json={"name": "Not An Admin"}).json()
    target = client.post("/api/operators", json={"name": "Target"}).json()

    resp = client.post(
        f"/api/operators/{target['id']}/role", json={"role": "admin", "acting_operator_id": non_admin["id"]}
    )
    assert resp.status_code == 403


def test_cannot_impersonate_a_pinned_admin_by_id_alone_to_self_promote(client):
    """Security-review finding, fixed: acting_operator_id alone used to be treated
    as proof of identity — anyone who learned a real admin's id (e.g. from GET
    /api/operators, which lists every operator's role) could cite it to grant
    *their own* unrelated operator the admin role, a full bypass of every role
    check this feature exists to enforce. The fix requires that admin's PIN too,
    same as every other admin-gated action."""
    # First operator ever -> auto-admin (see create_operator) — give it a real PIN,
    # the case that matters: an admin who *has* set a PIN must not be
    # impersonable by an attacker who only knows their id, not their PIN.
    real_admin = client.post("/api/operators", json={"name": "Real Admin", "pin": "9999"}).json()
    assert real_admin["role"] == "admin"

    attacker_operator = client.post("/api/operators", json={"name": "Attacker"}).json()
    assert attacker_operator["role"] == "operator"

    # Learn the real admin's id the same way an attacker could — the list endpoint.
    roster = client.get("/api/operators").json()
    assert any(o["id"] == real_admin["id"] and o["role"] == "admin" for o in roster)

    # Attempt to self-promote by citing the real admin's id, with no PIN.
    no_pin = client.post(
        f"/api/operators/{attacker_operator['id']}/role",
        json={"role": "admin", "acting_operator_id": real_admin["id"]},
    )
    assert no_pin.status_code == 401

    wrong_pin = client.post(
        f"/api/operators/{attacker_operator['id']}/role",
        json={"role": "admin", "acting_operator_id": real_admin["id"], "pin": "0000"},
    )
    assert wrong_pin.status_code == 401

    # The attacker's operator must still be at its original, unprivileged role.
    still_unprivileged = next(o for o in client.get("/api/operators").json() if o["id"] == attacker_operator["id"])
    assert still_unprivileged["role"] == "operator"

    # Confirms the endpoint itself is sound: the *real* admin, presenting the
    # correct PIN, can still grant roles normally.
    correct_pin = client.post(
        f"/api/operators/{attacker_operator['id']}/role",
        json={"role": "admin", "acting_operator_id": real_admin["id"], "pin": "9999"},
    )
    assert correct_pin.status_code == 200
