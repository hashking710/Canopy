import pytest
from aiohttp import web
from canopy_menusync_weedmaps import WeedmapsMenuSync

PORT = 18600


def set_env(monkeypatch, **overrides):
    env = {
        "CANOPY_WEEDMAPS_API_KEY": "wm-key-abc",
        "CANOPY_WEEDMAPS_LOCATION_ID": "loc-1",
        "CANOPY_WEEDMAPS_BASE_URL": f"http://127.0.0.1:{PORT}",
    }
    env.update(overrides)
    for key, value in env.items():
        monkeypatch.setenv(key, value)


class RecordingServer:
    """A real local HTTP server (not a mock) that records every request it
    receives and replies 200 — same pattern the METRC compliance-sync plugin's
    own tests use."""

    def __init__(self):
        self.requests: list[dict] = []
        self.status = 200

    async def handler(self, request: web.Request):
        body = await request.json()
        self.requests.append(
            {
                "method": request.method,
                "path": request.path,
                "query": dict(request.query),
                "headers": dict(request.headers),
                "body": body,
            }
        )
        return web.json_response({}, status=self.status)


@pytest.fixture
async def server():
    rec = RecordingServer()
    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", rec.handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", PORT)
    await site.start()
    try:
        yield rec
    finally:
        await runner.cleanup()


def make_item(**overrides):
    item = {
        "package_id": "pkg-1",
        "item_name": "GMO Flower",
        "weight_g": 453.6,
        "price_cents": 4500,
        "room_id": "vault",
        "strain_name": "GMO",
        "strain_type": "hybrid",
        "lineage": "Chemdog x Girl Scout Cookies",
        "thc_pct": 24.5,
        "cbd_pct": 0.3,
    }
    item.update(overrides)
    return item


async def test_pushes_one_request_per_item(server, monkeypatch):
    set_env(monkeypatch)
    sync = WeedmapsMenuSync()
    result = await sync.push_menu([make_item(), make_item(package_id="pkg-2")])

    assert result == {"pushed": 2, "skipped": 0}
    assert len(server.requests) == 2


async def test_auth_header_is_bearer_token(server, monkeypatch):
    set_env(monkeypatch)
    sync = WeedmapsMenuSync()
    await sync.push_menu([make_item()])

    assert server.requests[0]["headers"]["Authorization"] == "Bearer wm-key-abc"


async def test_location_id_sent_as_query_param(server, monkeypatch):
    set_env(monkeypatch)
    sync = WeedmapsMenuSync()
    await sync.push_menu([make_item()])

    assert server.requests[0]["query"] == {"location_id": "loc-1"}


async def test_request_body_carries_genetics_and_potency(server, monkeypatch):
    set_env(monkeypatch)
    sync = WeedmapsMenuSync()
    await sync.push_menu([make_item()])

    body = server.requests[0]["body"]
    assert body["external_id"] == "pkg-1"
    assert body["strain_name"] == "GMO"
    assert body["strain_type"] == "hybrid"
    assert body["lineage"] == "Chemdog x Girl Scout Cookies"
    assert body["thc_percentage"] == 24.5
    assert body["cbd_percentage"] == 0.3


async def test_a_failed_item_is_skipped_not_fatal_to_the_rest(server, monkeypatch):
    set_env(monkeypatch)
    server.status = 500
    sync = WeedmapsMenuSync()
    result = await sync.push_menu([make_item(), make_item(package_id="pkg-2")])

    assert result == {"pushed": 0, "skipped": 2}


async def test_push_menu_without_api_key_raises(monkeypatch):
    monkeypatch.delenv("CANOPY_WEEDMAPS_API_KEY", raising=False)
    sync = WeedmapsMenuSync()
    with pytest.raises(RuntimeError, match="CANOPY_WEEDMAPS_API_KEY"):
        await sync.push_menu([make_item()])


def test_plugin_metadata_is_set():
    assert WeedmapsMenuSync.plugin_name == "Weedmaps"
    assert "CANOPY_WEEDMAPS_API_KEY" in WeedmapsMenuSync.required_env_vars


def test_missing_api_key_warns_but_does_not_crash(monkeypatch, caplog):
    monkeypatch.delenv("CANOPY_WEEDMAPS_API_KEY", raising=False)
    with caplog.at_level("WARNING"):
        WeedmapsMenuSync()
    assert "isn't set" in caplog.text
