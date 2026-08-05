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


def test_unset_secret_reports_not_set(client):
    os.environ.pop(REAL_KEY, None)
    resp = client.get("/api/secrets")
    entry = next(s for s in resp.json() if s["key"] == REAL_KEY)
    assert entry["is_set"] is False
    assert entry["set_via_dashboard"] is False


def test_set_secret_takes_effect_immediately(client):
    resp = client.put(f"/api/secrets/{REAL_KEY}", json={"value": "test-api-key"})
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


def test_clear_secret_removes_it(client):
    client.put(f"/api/secrets/{REAL_KEY}", json={"value": "temp-key"})
    resp = client.delete(f"/api/secrets/{REAL_KEY}")
    assert resp.status_code == 200
    assert resp.json() == {"key": REAL_KEY, "is_set": False}
    assert os.environ.get(REAL_KEY) is None

    listed = client.get("/api/secrets").json()
    entry = next(s for s in listed if s["key"] == REAL_KEY)
    assert entry["is_set"] is False


def test_set_unknown_key_rejected(client):
    resp = client.put("/api/secrets/NOT_A_REAL_ENV_VAR", json={"value": "x"})
    assert resp.status_code == 400
    assert "unknown secret key" in resp.json()["detail"]


def test_set_empty_value_rejected(client):
    resp = client.put(f"/api/secrets/{REAL_KEY}", json={"value": "   "})
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"]


def test_clear_unknown_key_rejected(client):
    resp = client.delete("/api/secrets/NOT_A_REAL_ENV_VAR")
    assert resp.status_code == 400
