import pytest
from aiohttp import web
from canopy_adapter_ecowitt import EcowittAdapter, _flatten_readings
from canopy_agent.models import Room


def make_room(**adapter_config) -> Room:
    return Room(
        id="ecowitt-room", room_type="greenhouse", path="~/ecowitt-room",
        adapter_type="ecowitt", metric_config={}, adapter_config=adapter_config,
    )


# ---- pure response parsing — no network involved -----------------------------------


def test_flatten_readings_across_multiple_lists():
    body = {
        "common_list": [
            {"id": "0x02", "val": "77.5", "unit": "F"},
            {"id": "0x07", "val": "45", "unit": "%"},
        ],
        "soil_ch1": [{"id": "0x0D", "val": "38", "unit": "%"}],
    }
    assert _flatten_readings(body) == {"0x02": 77.5, "0x07": 45.0, "0x0D": 38.0}


def test_flatten_readings_skips_non_numeric_fields():
    body = {"common_list": [{"id": "0x02", "val": "77.5"}, {"id": "battery", "val": "Normal"}]}
    assert _flatten_readings(body) == {"0x02": 77.5}


def test_flatten_readings_ignores_non_list_keys():
    body = {"common_list": [{"id": "0x02", "val": "77.5"}], "some_metadata": {"version": "1.0"}}
    assert _flatten_readings(body) == {"0x02": 77.5}


def test_flatten_readings_empty_body():
    assert _flatten_readings({}) == {}


# ---- config validation --------------------------------------------------------------


async def test_read_without_host_raises():
    adapter = EcowittAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.host"):
        await adapter.read(make_room())


async def test_read_without_fields_raises():
    adapter = EcowittAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.fields"):
        await adapter.read(make_room(host="127.0.0.1"))


def test_plugin_metadata_is_set():
    assert EcowittAdapter.plugin_name == "Ecowitt (local LAN API)"
    assert "fields" in EcowittAdapter.config_schema


# ---- real end-to-end read against a real local HTTP server, matching Ecowitt's
# documented response shape — the strongest verification available without a real
# gateway. -----------------------------------------------------------------------------


async def test_read_from_a_real_server():
    async def handler(request):
        assert request.path == "/get_livedata_info"
        return web.json_response(
            {
                "common_list": [
                    {"id": "0x02", "val": "77.5", "unit": "F"},
                    {"id": "0x07", "val": "45", "unit": "%"},
                ],
                "soil_ch1": [{"id": "0x0D", "val": "38", "unit": "%"}],
            }
        )

    app = web.Application()
    app.router.add_get("/get_livedata_info", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 18101)
    await site.start()
    try:
        adapter = EcowittAdapter()
        room = make_room(
            host="127.0.0.1:18101",
            fields={"temp_f": "0x02", "rh_pct": "0x07", "soil_pct": "0x0D"},
        )
        values = await adapter.read(room)
        assert values == {"temp_f": 77.5, "rh_pct": 45.0, "soil_pct": 38.0}
    finally:
        await runner.cleanup()


async def test_missing_configured_field_raises_a_clear_error():
    async def handler(request):
        return web.json_response({"common_list": [{"id": "0x02", "val": "77.5"}]})

    app = web.Application()
    app.router.add_get("/get_livedata_info", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 18102)
    await site.start()
    try:
        adapter = EcowittAdapter()
        room = make_room(host="127.0.0.1:18102", fields={"co2_ppm": "0x99"})
        with pytest.raises(RuntimeError, match="no sensor with id '0x99'"):
            await adapter.read(room)
    finally:
        await runner.cleanup()
