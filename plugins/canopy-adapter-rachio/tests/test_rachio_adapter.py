import pytest
from aiohttp import web
import canopy_adapter_rachio
from canopy_adapter_rachio import RachioAdapter, is_zone_active
from canopy_agent.models import Room


def make_room(**adapter_config) -> Room:
    return Room(
        id="rachio-room", room_type="greenhouse", path="~/rachio-room",
        adapter_type="rachio", metric_config={}, adapter_config=adapter_config,
    )


# ---- zone-match logic — pure, no network involved ------------------------------------


def test_is_zone_active_matching_zone():
    assert is_zone_active({"zoneId": "zone-1", "type": "AUTOMATIC"}, "zone-1") is True


def test_is_zone_active_different_zone():
    assert is_zone_active({"zoneId": "zone-2"}, "zone-1") is False


def test_is_zone_active_empty_response_means_idle():
    assert is_zone_active({}, "zone-1") is False


# ---- config validation ----------------------------------------------------------------


async def test_read_without_api_key_raises(monkeypatch):
    monkeypatch.delenv("CANOPY_RACHIO_API_KEY", raising=False)
    adapter = RachioAdapter()
    with pytest.raises(RuntimeError, match="CANOPY_RACHIO_API_KEY"):
        await adapter.read(make_room(device_id="dev", zone_id="zone-1"))


async def test_read_without_device_or_zone_raises(monkeypatch):
    monkeypatch.setenv("CANOPY_RACHIO_API_KEY", "key")
    adapter = RachioAdapter()
    with pytest.raises(RuntimeError, match="device_id and adapter_config.zone_id"):
        await adapter.read(make_room())


def test_plugin_metadata_is_set():
    assert RachioAdapter.plugin_name == "Rachio (Cloud API)"
    assert "zone_id" in RachioAdapter.config_schema
    assert "CANOPY_RACHIO_API_KEY" in RachioAdapter.required_env_vars
    assert set(RachioAdapter.default_metric_config) == {"zone_active"}


# ---- real end-to-end read against a real local HTTP server --------------------------


async def test_read_zone_active_from_a_real_server(monkeypatch):
    monkeypatch.setenv("CANOPY_RACHIO_API_KEY", "test-key")
    received_headers = {}

    async def handler(request):
        received_headers.update(request.headers)
        return web.json_response({"zoneId": "zone-1", "type": "AUTOMATIC"})

    app = web.Application()
    app.router.add_get("/device/dev-1/current_schedule", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 18401)
    await site.start()
    try:
        monkeypatch.setattr(canopy_adapter_rachio, "API_BASE", "http://127.0.0.1:18401")
        adapter = RachioAdapter()
        values = await adapter.read(make_room(device_id="dev-1", zone_id="zone-1"))
        assert values == {"zone_active": 1.0}
        assert received_headers["Authorization"] == "Bearer test-key"
    finally:
        await runner.cleanup()


async def test_read_zone_idle_returns_zero(monkeypatch):
    monkeypatch.setenv("CANOPY_RACHIO_API_KEY", "test-key")

    async def handler(request):
        return web.Response(status=204)

    app = web.Application()
    app.router.add_get("/device/dev-1/current_schedule", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 18402)
    await site.start()
    try:
        monkeypatch.setattr(canopy_adapter_rachio, "API_BASE", "http://127.0.0.1:18402")
        adapter = RachioAdapter()
        values = await adapter.read(make_room(device_id="dev-1", zone_id="zone-1"))
        assert values == {"zone_active": 0.0}
    finally:
        await runner.cleanup()
