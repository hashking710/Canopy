import httpx
import pytest

from canopy_agent.routers.version import GITHUB_REPO, _compare_to_main, _current_sha


def test_current_sha_none_when_unset(monkeypatch):
    monkeypatch.delenv("CANOPY_GIT_SHA", raising=False)
    assert _current_sha() is None


def test_current_sha_none_for_the_dockerfile_default(monkeypatch):
    monkeypatch.setenv("CANOPY_GIT_SHA", "unknown")
    assert _current_sha() is None


def test_current_sha_returns_a_real_sha(monkeypatch):
    monkeypatch.setenv("CANOPY_GIT_SHA", "abc1234def")
    assert _current_sha() == "abc1234def"


def test_get_version_endpoint(client, monkeypatch):
    monkeypatch.setenv("CANOPY_GIT_SHA", "abc1234def5678")
    resp = client.get("/api/version")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sha"] == "abc1234def5678"
    assert body["short_sha"] == "abc1234"
    assert body["repo"] == GITHUB_REPO


def test_get_version_endpoint_unset(client, monkeypatch):
    monkeypatch.delenv("CANOPY_GIT_SHA", raising=False)
    resp = client.get("/api/version")
    assert resp.json() == {"sha": None, "short_sha": None, "repo": GITHUB_REPO}


def _mock_transport(status_code: int, json_body: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=json_body or {})

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_compare_up_to_date():
    transport = _mock_transport(200, {"ahead_by": 0, "behind_by": 0, "commits": []})
    result = await _compare_to_main("current123", transport=transport)
    assert result == {
        "checked": True,
        "up_to_date": True,
        "commits_behind": 0,
        "latest_sha": "current123",
        "latest_short_sha": "current",
        "compare_url": f"https://github.com/{GITHUB_REPO}/compare/current123...main",
    }


@pytest.mark.asyncio
async def test_compare_behind():
    transport = _mock_transport(
        200,
        {"ahead_by": 3, "behind_by": 0, "commits": [{"sha": "older1"}, {"sha": "newer_tip_sha"}]},
    )
    result = await _compare_to_main("current123", transport=transport)
    assert result["checked"] is True
    assert result["up_to_date"] is False
    assert result["commits_behind"] == 3
    assert result["latest_sha"] == "newer_tip_sha"
    assert result["latest_short_sha"] == "newer_t"


@pytest.mark.asyncio
async def test_compare_unknown_commit_404():
    transport = _mock_transport(404)
    result = await _compare_to_main("not-a-real-sha", transport=transport)
    assert result["checked"] is False
    assert "doesn't recognize" in result["reason"]


@pytest.mark.asyncio
async def test_compare_github_error_status():
    transport = _mock_transport(503)
    result = await _compare_to_main("current123", transport=transport)
    assert result["checked"] is False
    assert "503" in result["reason"]


@pytest.mark.asyncio
async def test_compare_network_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no network", request=request)

    transport = httpx.MockTransport(handler)
    result = await _compare_to_main("current123", transport=transport)
    assert result["checked"] is False
    assert "couldn't reach GitHub" in result["reason"]


def test_check_endpoint_with_no_version_baked_in(client, monkeypatch):
    monkeypatch.delenv("CANOPY_GIT_SHA", raising=False)
    resp = client.get("/api/version/check")
    assert resp.status_code == 200
    body = resp.json()
    assert body["checked"] is False
    assert "no version baked in" in body["reason"]
