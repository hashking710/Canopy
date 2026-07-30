from fastapi import FastAPI
from fastapi.testclient import TestClient

from canopy_agent.services.demo_rate_limit import DemoRateLimitMiddleware


def _make_app(limit: int = 3, window_seconds: float = 60) -> FastAPI:
    app = FastAPI()
    app.add_middleware(DemoRateLimitMiddleware, limit=limit, window_seconds=window_seconds)

    @app.get("/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_allows_requests_under_the_limit():
    client = TestClient(_make_app(limit=3))
    for _ in range(3):
        assert client.get("/ping").status_code == 200


def test_blocks_requests_over_the_limit_with_429():
    client = TestClient(_make_app(limit=2))
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 200
    blocked = client.get("/ping")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_tracks_distinct_ips_independently():
    client = TestClient(_make_app(limit=1))
    first = client.get("/ping", headers={"x-forwarded-for": "1.1.1.1"})
    second = client.get("/ping", headers={"x-forwarded-for": "2.2.2.2"})
    assert first.status_code == 200
    assert second.status_code == 200
    # Same IP again, over its own limit now.
    third = client.get("/ping", headers={"x-forwarded-for": "1.1.1.1"})
    assert third.status_code == 429


def test_window_resets_after_expiry():
    client = TestClient(_make_app(limit=1, window_seconds=0.05))
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 429
    import time

    time.sleep(0.1)
    assert client.get("/ping").status_code == 200
