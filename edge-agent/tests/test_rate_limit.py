import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from canopy_agent.services.rate_limit import RateLimitMiddleware


def _make_app(
    general_limit: int = 3,
    general_window_seconds: float = 60,
    auth_failure_limit: int = 2,
    auth_failure_window_seconds: float = 60,
) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        general_limit=general_limit,
        general_window_seconds=general_window_seconds,
        auth_failure_limit=auth_failure_limit,
        auth_failure_window_seconds=auth_failure_window_seconds,
    )

    @app.get("/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/needs-auth")
    def needs_auth(fail: bool = False):
        from fastapi import HTTPException

        if fail:
            raise HTTPException(status_code=401, detail="nope")
        return {"ok": True}

    return app


# ---- general tier — same shape as the old demo-only limiter it replaces --------


def test_allows_requests_under_the_general_limit():
    client = TestClient(_make_app(general_limit=3))
    for _ in range(3):
        assert client.get("/ping").status_code == 200


def test_blocks_requests_over_the_general_limit_with_429():
    client = TestClient(_make_app(general_limit=2))
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 200
    blocked = client.get("/ping")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_tracks_distinct_ips_independently():
    client = TestClient(_make_app(general_limit=1))
    first = client.get("/ping", headers={"x-forwarded-for": "1.1.1.1"})
    second = client.get("/ping", headers={"x-forwarded-for": "2.2.2.2"})
    assert first.status_code == 200
    assert second.status_code == 200
    third = client.get("/ping", headers={"x-forwarded-for": "1.1.1.1"})
    assert third.status_code == 429


def test_general_window_resets_after_expiry():
    client = TestClient(_make_app(general_limit=1, general_window_seconds=0.05))
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 429
    time.sleep(0.1)
    assert client.get("/ping").status_code == 200


# ---- auth-failure tier — the new part: repeated 401s throttle the whole IP -----


def test_repeated_401s_eventually_get_throttled_regardless_of_general_limit():
    client = TestClient(
        _make_app(general_limit=100, auth_failure_limit=2, auth_failure_window_seconds=60)
    )
    assert client.get("/needs-auth", params={"fail": True}).status_code == 401
    assert client.get("/needs-auth", params={"fail": True}).status_code == 401
    # Third request from the same IP is blocked outright, even before reaching the
    # route — the whole point: slows a token-guessing sweep, not just caps volume.
    blocked = client.get("/needs-auth", params={"fail": True})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_auth_failure_throttle_blocks_even_a_correct_attempt_once_tripped():
    """A brute-forcer's Nth guess might finally be right — the throttle must not
    wave a later, correct request through just because it succeeded."""
    client = TestClient(
        _make_app(general_limit=100, auth_failure_limit=1, auth_failure_window_seconds=60)
    )
    assert client.get("/needs-auth", params={"fail": True}).status_code == 401
    # Would otherwise succeed (fail=False), but the IP is already throttled.
    blocked = client.get("/needs-auth", params={"fail": False})
    assert blocked.status_code == 429


def test_successful_requests_never_count_toward_the_auth_failure_tier():
    client = TestClient(
        _make_app(general_limit=100, auth_failure_limit=2, auth_failure_window_seconds=60)
    )
    for _ in range(10):
        assert client.get("/needs-auth", params={"fail": False}).status_code == 200


def test_auth_failure_tracks_distinct_ips_independently():
    client = TestClient(_make_app(general_limit=100, auth_failure_limit=1))
    assert client.get("/needs-auth", params={"fail": True}, headers={"x-forwarded-for": "1.1.1.1"}).status_code == 401
    # Different IP, untouched by the first one's failures.
    assert client.get("/needs-auth", params={"fail": True}, headers={"x-forwarded-for": "2.2.2.2"}).status_code == 401
