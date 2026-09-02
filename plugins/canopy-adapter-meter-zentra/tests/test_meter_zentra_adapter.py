import pytest
from aiohttp import web
import canopy_adapter_meter_zentra
from canopy_adapter_meter_zentra import MeterZentraAdapter, _extract_latest
from canopy_agent.models import Room

PORT = 18700


def make_room(**adapter_config) -> Room:
    return Room(
        id="meter-room", room_type="greenhouse", path="~/meter-room",
        adapter_type="meter_zentra", metric_config={}, adapter_config=adapter_config,
    )


# ---- response parsing — pure, no network involved -----------------------------------


def test_extract_latest_from_a_data_list():
    body = {"data": [{"sensor_label": "Water Content", "value": 32.1}, {"sensor_label": "Temperature", "value": 21.5}]}
    values = _extract_latest(body, {"soil_pct": "Water Content", "temp_f": "Temperature"}, "z6-1")
    assert values == {"soil_pct": 32.1, "temp_f": 21.5}


def test_extract_latest_from_a_bare_list():
    body = [{"label": "Water Content", "value_1": 40.0}]
    values = _extract_latest(body, {"soil_pct": "Water Content"}, "z6-1")
    assert values == {"soil_pct": 40.0}


def test_extract_latest_missing_label_raises():
    body = {"data": [{"sensor_label": "Temperature", "value": 21.5}]}
    with pytest.raises(RuntimeError, match="no reading found with sensor label 'Water Content'"):
        _extract_latest(body, {"soil_pct": "Water Content"}, "z6-1")


def test_extract_latest_unrecognized_envelope_raises_with_diagnostic():
    body = {"something_else": []}
    with pytest.raises(RuntimeError, match="no recognizable reading list"):
        _extract_latest(body, {"soil_pct": "Water Content"}, "z6-1")


# ---- config validation ----------------------------------------------------------------


async def test_read_without_api_key_raises(monkeypatch):
    monkeypatch.delenv("CANOPY_METER_API_KEY", raising=False)
    adapter = MeterZentraAdapter()
    with pytest.raises(RuntimeError, match="CANOPY_METER_API_KEY"):
        await adapter.read(make_room(device_id="z6-1", fields={"soil_pct": "Water Content"}))


async def test_read_without_device_id_raises(monkeypatch):
    monkeypatch.setenv("CANOPY_METER_API_KEY", "key")
    adapter = MeterZentraAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.device_id"):
        await adapter.read(make_room(fields={"soil_pct": "Water Content"}))


def test_plugin_metadata_is_set():
    assert MeterZentraAdapter.plugin_name == "METER Group ZENTRA Cloud"
    assert "device_id" in MeterZentraAdapter.config_schema
    assert "CANOPY_METER_API_KEY" in MeterZentraAdapter.required_env_vars


# ---- real end-to-end read against a real local HTTP server --------------------------


async def test_read_from_a_real_server(monkeypatch):
    monkeypatch.setenv("CANOPY_METER_API_KEY", "test-key")
    received = {}

    async def handler(request):
        received["headers"] = dict(request.headers)
        received["query"] = dict(request.query)
        return web.json_response({"data": [{"sensor_label": "Water Content", "value": 32.1}]})

    app = web.Application()
    app.router.add_get("/v5/devices/z6-1/data", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", PORT)
    await site.start()
    try:
        monkeypatch.setattr(canopy_adapter_meter_zentra, "API_BASE", f"http://127.0.0.1:{PORT}/v5")
        adapter = MeterZentraAdapter()
        values = await adapter.read(make_room(device_id="z6-1", fields={"soil_pct": "Water Content"}))

        assert values == {"soil_pct": 32.1}
        assert received["headers"]["X-API-Key"] == "test-key"
        assert received["query"] == {"direction": "descending", "units": "metric"}
    finally:
        await runner.cleanup()


async def test_non_200_response_raises(monkeypatch):
    monkeypatch.setenv("CANOPY_METER_API_KEY", "test-key")

    async def handler(request):
        return web.Response(status=401, text="invalid api key")

    app = web.Application()
    app.router.add_get("/v5/devices/z6-1/data", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", PORT)
    await site.start()
    try:
        monkeypatch.setattr(canopy_adapter_meter_zentra, "API_BASE", f"http://127.0.0.1:{PORT}/v5")
        adapter = MeterZentraAdapter()
        with pytest.raises(RuntimeError, match="HTTP 401"):
            await adapter.read(make_room(device_id="z6-1", fields={"soil_pct": "Water Content"}))
    finally:
        await runner.cleanup()
