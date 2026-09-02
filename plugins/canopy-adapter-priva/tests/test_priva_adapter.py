import pytest
from aiohttp import web
import canopy_adapter_priva
from canopy_adapter_priva import PrivaAdapter
from canopy_agent.models import Room

PORT = 18900


def make_room(**adapter_config) -> Room:
    return Room(
        id="priva-room", room_type="greenhouse", path="~/priva-room",
        adapter_type="priva", metric_config={}, adapter_config=adapter_config,
    )


def set_env(monkeypatch):
    monkeypatch.setenv("CANOPY_PRIVA_CLIENT_ID", "client-abc")
    monkeypatch.setenv("CANOPY_PRIVA_CLIENT_SECRET", "secret-xyz")
    monkeypatch.setenv("CANOPY_PRIVA_API_BASE_URL", "https://example-customer.priva.com")


async def test_read_without_credentials_raises(monkeypatch):
    monkeypatch.delenv("CANOPY_PRIVA_CLIENT_ID", raising=False)
    monkeypatch.delenv("CANOPY_PRIVA_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("CANOPY_PRIVA_API_BASE_URL", "https://x.priva.com")
    adapter = PrivaAdapter()
    with pytest.raises(RuntimeError, match="CANOPY_PRIVA_CLIENT_ID"):
        await adapter.read(make_room(reference_id="ref-1"))


async def test_read_without_base_url_raises(monkeypatch):
    set_env(monkeypatch)
    monkeypatch.delenv("CANOPY_PRIVA_API_BASE_URL", raising=False)
    adapter = PrivaAdapter()
    with pytest.raises(RuntimeError, match="CANOPY_PRIVA_API_BASE_URL"):
        await adapter.read(make_room(reference_id="ref-1"))


async def test_read_without_reference_id_raises(monkeypatch):
    set_env(monkeypatch)
    adapter = PrivaAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.reference_id"):
        await adapter.read(make_room())


def test_plugin_metadata_is_set():
    assert PrivaAdapter.plugin_name == "Priva"
    assert "reference_id" in PrivaAdapter.config_schema
    assert "CANOPY_PRIVA_CLIENT_ID" in PrivaAdapter.required_env_vars
    assert "CANOPY_PRIVA_API_BASE_URL" in PrivaAdapter.required_env_vars


# ---- real OAuth2 token acquisition against a real local HTTP server -----------------


async def test_acquires_a_real_token_before_hitting_the_unimplemented_read(monkeypatch):
    """The token flow is the confirmed part of this integration (see module
    docstring) — this proves it actually runs a real client_credentials exchange
    before failing on the genuinely-unimplemented telemetry read."""
    set_env(monkeypatch)
    token_requests = []

    async def token_handler(request):
        body = await request.post()
        token_requests.append(dict(body))
        return web.json_response({"access_token": "tok-123", "expires_in": 3600})

    app = web.Application()
    app.router.add_post("/connect/token", token_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", PORT)
    await site.start()
    try:
        monkeypatch.setattr(canopy_adapter_priva, "TOKEN_URL", f"http://127.0.0.1:{PORT}/connect/token")
        adapter = PrivaAdapter()
        with pytest.raises(NotImplementedError, match="Realtime Data API"):
            await adapter.read(make_room(reference_id="ref-1"))

        assert token_requests[0] == {
            "grant_type": "client_credentials", "client_id": "client-abc", "client_secret": "secret-xyz",
        }
    finally:
        await runner.cleanup()


async def test_failed_token_request_raises_before_the_unimplemented_error(monkeypatch):
    set_env(monkeypatch)

    async def token_handler(request):
        return web.Response(status=401, text="invalid client")

    app = web.Application()
    app.router.add_post("/connect/token", token_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", PORT)
    await site.start()
    try:
        monkeypatch.setattr(canopy_adapter_priva, "TOKEN_URL", f"http://127.0.0.1:{PORT}/connect/token")
        adapter = PrivaAdapter()
        with pytest.raises(RuntimeError, match="token request returned HTTP 401"):
            await adapter.read(make_room(reference_id="ref-1"))
    finally:
        await runner.cleanup()
