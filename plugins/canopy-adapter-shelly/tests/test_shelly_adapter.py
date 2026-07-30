import pytest
from aiohttp import web
from canopy_adapter_shelly import ShellyAdapter, _parse_gen1_status, _parse_gen2_status
from canopy_agent.models import Room


def make_room(**adapter_config) -> Room:
    return Room(
        id="shelly-room", room_type="greenhouse", path="~/shelly-room",
        adapter_type="shelly", metric_config={}, adapter_config=adapter_config,
    )


# ---- pure response parsing, real documented shapes — no network involved ----------


def test_parse_gen1_status_real_shape():
    # A real Shelly Plug S /status response shape (trimmed to the relevant fields).
    body = {
        "wifi_sta": {"connected": True},
        "meters": [{"power": 34.5, "is_valid": True}],
        "temperature": 45.2,
        "overtemperature": False,
        "relays": [{"ison": True}],
    }
    assert _parse_gen1_status(body) == {"power_w": 34.5, "temp_c": 45.2}


def test_parse_gen1_status_missing_meter():
    assert _parse_gen1_status({"temperature": 30.0}) == {"temp_c": 30.0}


def test_parse_gen2_status_real_shape():
    # A real Shelly Plus Plug S RPC Switch.GetStatus response shape.
    body = {
        "id": 0, "source": "init", "output": True,
        "apower": 12.3, "voltage": 230.5, "current": 0.053,
        "aenergy": {"total": 456.7, "by_minute": [0, 0, 0]},
        "temperature": {"tC": 35.2, "tF": 95.4},
    }
    assert _parse_gen2_status(body) == {
        "power_w": 12.3, "voltage_v": 230.5, "current_a": 0.053,
        "energy_wh": 456.7, "temp_c": 35.2,
    }


def test_parse_gen2_status_output_off_still_reports_zero_power():
    body = {"id": 0, "output": False, "apower": 0.0, "voltage": 231.0, "current": 0.0, "aenergy": {"total": 100.0}}
    values = _parse_gen2_status(body)
    assert values["power_w"] == 0.0


# ---- config validation --------------------------------------------------------------


async def test_read_without_host_raises():
    adapter = ShellyAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.host"):
        await adapter.read(make_room())


async def test_read_with_unknown_generation_raises():
    adapter = ShellyAdapter()
    with pytest.raises(RuntimeError, match="unknown adapter_config.generation"):
        await adapter.read(make_room(host="127.0.0.1", generation=3))


def test_plugin_metadata_is_set():
    assert ShellyAdapter.plugin_name == "Shelly (local API)"
    assert "host" in ShellyAdapter.config_schema


# ---- real end-to-end read against a real local HTTP server, matching Shelly's real
# wire shape — the strongest verification available without physical hardware. -------


async def test_read_from_a_real_gen1_server():
    async def handler(request):
        assert request.path == "/status"
        return web.json_response({"meters": [{"power": 22.5, "is_valid": True}], "temperature": 40.1})

    app = web.Application()
    app.router.add_get("/status", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 18001)
    await site.start()
    try:
        adapter = ShellyAdapter()
        room = make_room(host="127.0.0.1:18001", generation=1)
        values = await adapter.read(room)
        assert values == {"power_w": 22.5, "temp_c": 40.1}
    finally:
        await runner.cleanup()


async def test_read_from_a_real_gen2_server():
    async def handler(request):
        assert request.path == "/rpc/Switch.GetStatus"
        assert request.query["id"] == "1"
        return web.json_response(
            {"id": 1, "apower": 5.5, "voltage": 229.8, "current": 0.024, "aenergy": {"total": 10.0}}
        )

    app = web.Application()
    app.router.add_get("/rpc/Switch.GetStatus", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 18002)
    await site.start()
    try:
        adapter = ShellyAdapter()
        room = make_room(host="127.0.0.1:18002", generation=2, switch_id=1)
        values = await adapter.read(room)
        assert values == {"power_w": 5.5, "voltage_v": 229.8, "current_a": 0.024, "energy_wh": 10.0}
    finally:
        await runner.cleanup()


async def test_non_200_response_raises():
    async def handler(request):
        return web.Response(status=500)

    app = web.Application()
    app.router.add_get("/status", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 18003)
    await site.start()
    try:
        adapter = ShellyAdapter()
        room = make_room(host="127.0.0.1:18003", generation=1)
        with pytest.raises(RuntimeError, match="HTTP 500"):
            await adapter.read(room)
    finally:
        await runner.cleanup()
