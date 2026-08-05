import pytest
from aiohttp import web
import canopy_adapter_govee
from canopy_adapter_govee import GoveeAdapter, _parse_capabilities
from canopy_agent.models import Room


def make_room(**adapter_config) -> Room:
    return Room(
        id="govee-room", room_type="greenhouse", path="~/govee-room",
        adapter_type="govee", metric_config={}, adapter_config=adapter_config,
    )


# ---- response parsing — pure, no network involved -----------------------------------


def test_parse_capabilities_extracts_temp_and_humidity():
    capabilities = [
        {"type": "devices.capabilities.property", "instance": "sensorTemperature", "state": {"value": 22.5}},
        {"type": "devices.capabilities.property", "instance": "sensorHumidity", "state": {"value": 55}},
        {"type": "devices.capabilities.property", "instance": "online", "state": {"value": True}},
    ]
    values = _parse_capabilities(capabilities)
    assert values["temp_f"] == pytest.approx(22.5 * 9 / 5 + 32)
    assert values["rh_pct"] == 55.0


def test_parse_capabilities_ignores_unrelated_ones():
    capabilities = [{"type": "devices.capabilities.on_off", "instance": "powerSwitch", "state": {"value": 1}}]
    assert _parse_capabilities(capabilities) == {}


def test_parse_capabilities_empty_list():
    assert _parse_capabilities([]) == {}


# ---- config validation ----------------------------------------------------------------


async def test_read_without_api_key_raises(monkeypatch):
    monkeypatch.delenv("CANOPY_GOVEE_API_KEY", raising=False)
    adapter = GoveeAdapter()
    with pytest.raises(RuntimeError, match="CANOPY_GOVEE_API_KEY"):
        await adapter.read(make_room(sku="H5179", device="AA:BB"))


async def test_read_without_sku_or_device_raises(monkeypatch):
    monkeypatch.setenv("CANOPY_GOVEE_API_KEY", "key")
    adapter = GoveeAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.sku"):
        await adapter.read(make_room())


def test_plugin_metadata_is_set():
    assert GoveeAdapter.plugin_name == "Govee (Cloud API)"
    assert "sku" in GoveeAdapter.config_schema
    assert "CANOPY_GOVEE_API_KEY" in GoveeAdapter.required_env_vars
    assert set(GoveeAdapter.default_metric_config) == {"temp_f", "rh_pct"}


# ---- real end-to-end read against a real local HTTP server --------------------------


async def test_read_from_a_real_server(monkeypatch):
    monkeypatch.setenv("CANOPY_GOVEE_API_KEY", "test-key")
    received_headers = {}

    async def handler(request):
        received_headers.update(request.headers)
        body = await request.json()
        assert body["payload"] == {"sku": "H5179", "device": "AA:BB:CC:DD:EE:FF"}
        return web.json_response(
            {
                "requestId": body["requestId"],
                "code": 200,
                "msg": "success",
                "payload": {
                    "sku": "H5179",
                    "device": "AA:BB:CC:DD:EE:FF",
                    "capabilities": [
                        {"type": "devices.capabilities.property", "instance": "sensorTemperature", "state": {"value": 21.0}},
                        {"type": "devices.capabilities.property", "instance": "sensorHumidity", "state": {"value": 48}},
                    ],
                },
            }
        )

    app = web.Application()
    app.router.add_post("/router/api/v1/device/state", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 18301)
    await site.start()
    try:
        monkeypatch.setattr(canopy_adapter_govee, "API_BASE", "http://127.0.0.1:18301/router/api/v1")
        adapter = GoveeAdapter()
        values = await adapter.read(make_room(sku="H5179", device="AA:BB:CC:DD:EE:FF"))

        assert values["temp_f"] == pytest.approx(21.0 * 9 / 5 + 32)
        assert values["rh_pct"] == 48.0
        assert received_headers["Govee-API-Key"] == "test-key"
    finally:
        await runner.cleanup()


async def test_error_code_raises(monkeypatch):
    monkeypatch.setenv("CANOPY_GOVEE_API_KEY", "test-key")

    async def handler(request):
        return web.json_response({"requestId": "x", "code": 401, "msg": "invalid API key"})

    app = web.Application()
    app.router.add_post("/router/api/v1/device/state", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 18302)
    await site.start()
    try:
        monkeypatch.setattr(canopy_adapter_govee, "API_BASE", "http://127.0.0.1:18302/router/api/v1")
        adapter = GoveeAdapter()
        with pytest.raises(RuntimeError, match="invalid API key"):
            await adapter.read(make_room(sku="H5179", device="AA:BB"))
    finally:
        await runner.cleanup()
