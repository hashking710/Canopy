import pytest
from aiohttp import web
from canopy_menusync_weedmaps import WeedmapsMenuSync

PORT = 18600


def set_env(monkeypatch, **overrides):
    env = {
        "CANOPY_WEEDMAPS_CLIENT_ID": "client-abc",
        "CANOPY_WEEDMAPS_CLIENT_SECRET": "secret-xyz",
        "CANOPY_WEEDMAPS_MENU_ID": "menu-1",
        "CANOPY_WEEDMAPS_TOKEN_URL": f"http://127.0.0.1:{PORT}/auth/token",
        "CANOPY_WEEDMAPS_BASE_URL": f"http://127.0.0.1:{PORT}/wm",
    }
    env.update(overrides)
    for key, value in env.items():
        monkeypatch.setenv(key, value)


class RecordingServer:
    """A real local HTTP server (not a mock) serving both the OAuth2 token endpoint
    and the menu-item upsert endpoint, recording every request — same "real local
    server, no live account" verification pattern the METRC compliance-sync plugin's
    own tests use."""

    def __init__(self):
        self.requests: list[dict] = []
        self.item_status = 200
        self.token_status = 200
        self.token_expires_in = 1209600  # 14 days, matches Weedmaps' documented default

    async def token_handler(self, request: web.Request):
        body = await request.json()
        self.requests.append({"path": request.path, "method": request.method, "body": body})
        if self.token_status != 200:
            return web.json_response({"error": "invalid_client"}, status=self.token_status)
        return web.json_response({"access_token": "tok-123", "expires_in": self.token_expires_in})

    async def item_handler(self, request: web.Request):
        body = await request.json()
        self.requests.append(
            {
                "path": request.path,
                "method": request.method,
                "headers": dict(request.headers),
                "body": body,
            }
        )
        return web.json_response({}, status=self.item_status)


@pytest.fixture
async def server():
    rec = RecordingServer()
    app = web.Application()
    app.router.add_post("/auth/token", rec.token_handler)
    app.router.add_put("/wm/menus/{menu_id}/items/external/{external_id}", rec.item_handler)
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


async def test_acquires_a_token_before_pushing(server, monkeypatch):
    set_env(monkeypatch)
    sync = WeedmapsMenuSync()
    await sync.push_menu([make_item()])

    token_reqs = [r for r in server.requests if r["path"] == "/auth/token"]
    assert len(token_reqs) == 1
    assert token_reqs[0]["body"] == {"client_id": "client-abc", "client_secret": "secret-xyz", "grant_type": "client_credentials"}


async def test_token_is_cached_across_multiple_push_calls(server, monkeypatch):
    set_env(monkeypatch)
    sync = WeedmapsMenuSync()
    await sync.push_menu([make_item()])
    await sync.push_menu([make_item(package_id="pkg-2")])

    token_reqs = [r for r in server.requests if r["path"] == "/auth/token"]
    assert len(token_reqs) == 1  # not re-fetched for the second call


async def test_puts_to_the_real_menu_item_endpoint(server, monkeypatch):
    set_env(monkeypatch)
    sync = WeedmapsMenuSync()
    result = await sync.push_menu([make_item(), make_item(package_id="pkg-2")])

    assert result == {"pushed": 2, "skipped": 0}
    item_reqs = [r for r in server.requests if r["path"] != "/auth/token"]
    assert {r["path"] for r in item_reqs} == {
        "/wm/menus/menu-1/items/external/pkg-1",
        "/wm/menus/menu-1/items/external/pkg-2",
    }
    assert all(r["method"] == "PUT" for r in item_reqs)


async def test_auth_header_is_bearer_token(server, monkeypatch):
    set_env(monkeypatch)
    sync = WeedmapsMenuSync()
    await sync.push_menu([make_item()])

    item_req = next(r for r in server.requests if r["path"] != "/auth/token")
    assert item_req["headers"]["Authorization"] == "Bearer tok-123"


async def test_request_body_shape_matches_the_real_weedmaps_schema(server, monkeypatch):
    set_env(monkeypatch)
    sync = WeedmapsMenuSync()
    await sync.push_menu([make_item()])

    body = next(r for r in server.requests if r["path"] != "/auth/token")["body"]
    assert body["name"] == "GMO Flower"
    assert body["genetics"] == "hybrid"
    assert "lineage" not in body  # no real Weedmaps field for this — must not be sent
    assert body["cannabinoids"] == [
        {"slug": "thc", "percentage": {"min": 24.5, "max": 24.5}},
        {"slug": "cbd", "percentage": {"min": 0.3, "max": 0.3}},
    ]
    variant = body["variants"][0]
    assert variant["price"] == {"amount": 45.0, "currency": "USD"}
    assert variant["weight"] == {"value": 453.6, "unit": "g"}


async def test_unknown_strain_type_omits_genetics_field(server, monkeypatch):
    set_env(monkeypatch)
    sync = WeedmapsMenuSync()
    await sync.push_menu([make_item(strain_type=None)])

    body = next(r for r in server.requests if r["path"] != "/auth/token")["body"]
    assert "genetics" not in body


async def test_no_potency_omits_cannabinoids_field(server, monkeypatch):
    set_env(monkeypatch)
    sync = WeedmapsMenuSync()
    await sync.push_menu([make_item(thc_pct=None, cbd_pct=None)])

    body = next(r for r in server.requests if r["path"] != "/auth/token")["body"]
    assert "cannabinoids" not in body


async def test_a_failed_item_is_skipped_not_fatal_to_the_rest(server, monkeypatch):
    set_env(monkeypatch)
    server.item_status = 500
    sync = WeedmapsMenuSync()
    result = await sync.push_menu([make_item(), make_item(package_id="pkg-2")])

    assert result == {"pushed": 0, "skipped": 2}


async def test_failed_token_request_raises(server, monkeypatch):
    set_env(monkeypatch)
    server.token_status = 401
    sync = WeedmapsMenuSync()
    with pytest.raises(RuntimeError, match="token request returned HTTP 401"):
        await sync.push_menu([make_item()])


async def test_push_menu_without_credentials_raises(monkeypatch):
    monkeypatch.delenv("CANOPY_WEEDMAPS_CLIENT_ID", raising=False)
    monkeypatch.delenv("CANOPY_WEEDMAPS_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("CANOPY_WEEDMAPS_MENU_ID", raising=False)
    sync = WeedmapsMenuSync()
    with pytest.raises(RuntimeError, match="CANOPY_WEEDMAPS_CLIENT_ID"):
        await sync.push_menu([make_item()])


def test_plugin_metadata_is_set():
    assert WeedmapsMenuSync.plugin_name == "Weedmaps"
    assert "CANOPY_WEEDMAPS_CLIENT_ID" in WeedmapsMenuSync.required_env_vars
    assert "CANOPY_WEEDMAPS_CLIENT_SECRET" in WeedmapsMenuSync.required_env_vars
    assert "CANOPY_WEEDMAPS_MENU_ID" in WeedmapsMenuSync.required_env_vars


def test_missing_credentials_warns_but_does_not_crash(monkeypatch, caplog):
    monkeypatch.delenv("CANOPY_WEEDMAPS_CLIENT_ID", raising=False)
    monkeypatch.delenv("CANOPY_WEEDMAPS_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("CANOPY_WEEDMAPS_MENU_ID", raising=False)
    with caplog.at_level("WARNING"):
        WeedmapsMenuSync()
    assert "aren't all set" in caplog.text
