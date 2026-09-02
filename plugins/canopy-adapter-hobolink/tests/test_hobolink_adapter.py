import pytest
from aiohttp import web
import canopy_adapter_hobolink
from canopy_adapter_hobolink import HobolinkAdapter, _extract_latest
from canopy_agent.models import Room

PORT = 18800


def make_room(**adapter_config) -> Room:
    return Room(
        id="hobo-room", room_type="greenhouse", path="~/hobo-room",
        adapter_type="hobolink", metric_config={}, adapter_config=adapter_config,
    )


def set_env(monkeypatch):
    monkeypatch.setenv("CANOPY_HOBOLINK_CLIENT_ID", "client-abc")
    monkeypatch.setenv("CANOPY_HOBOLINK_CLIENT_SECRET", "secret-xyz")


# ---- response parsing — pure, no network involved -----------------------------------


def test_extract_latest_from_series_shape():
    body = {"series": [{"sensor_measurement_type": "Temperature", "readings": [{"value": 20.0}, {"value": 21.5}]}]}
    values = _extract_latest(body, {"temp_f": "Temperature"}, "20958060")
    assert values == {"temp_f": 21.5}  # last reading in the list wins (most recent)


def test_extract_latest_missing_label_raises():
    body = {"series": [{"sensor_measurement_type": "RH", "readings": [{"value": 50.0}]}]}
    with pytest.raises(RuntimeError, match="no series found with sensor label 'Temperature'"):
        _extract_latest(body, {"temp_f": "Temperature"}, "20958060")


def test_extract_latest_unrecognized_envelope_raises_with_diagnostic():
    with pytest.raises(RuntimeError, match="no recognizable data series"):
        _extract_latest({"unexpected": []}, {"temp_f": "Temperature"}, "20958060")


def test_extract_latest_empty_readings_raises():
    body = {"series": [{"sensor_measurement_type": "Temperature", "readings": []}]}
    with pytest.raises(RuntimeError, match="no readings in the lookback window"):
        _extract_latest(body, {"temp_f": "Temperature"}, "20958060")


# ---- config validation ----------------------------------------------------------------


async def test_read_without_credentials_raises(monkeypatch):
    monkeypatch.delenv("CANOPY_HOBOLINK_CLIENT_ID", raising=False)
    monkeypatch.delenv("CANOPY_HOBOLINK_CLIENT_SECRET", raising=False)
    adapter = HobolinkAdapter()
    with pytest.raises(RuntimeError, match="CANOPY_HOBOLINK_CLIENT_ID"):
        await adapter.read(make_room(user_id="1", logger_sn="20958060", fields={"temp_f": "Temperature"}))


async def test_read_without_logger_sn_raises(monkeypatch):
    set_env(monkeypatch)
    adapter = HobolinkAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.logger_sn"):
        await adapter.read(make_room(user_id="1", fields={"temp_f": "Temperature"}))


def test_plugin_metadata_is_set():
    assert HobolinkAdapter.plugin_name == "Onset HOBOlink"
    assert "logger_sn" in HobolinkAdapter.config_schema
    assert "CANOPY_HOBOLINK_CLIENT_ID" in HobolinkAdapter.required_env_vars


# ---- real end-to-end read against a real local HTTP server --------------------------


async def test_read_from_a_real_server(monkeypatch):
    set_env(monkeypatch)
    token_requests = []
    data_requests = []

    async def token_handler(request):
        body = await request.post()
        token_requests.append(dict(body))
        return web.json_response({"access_token": "tok-123", "expires_in": 3600})

    async def data_handler(request):
        data_requests.append({"headers": dict(request.headers), "query": dict(request.query)})
        return web.json_response({"series": [{"sensor_measurement_type": "Temperature", "readings": [{"value": 21.5}]}]})

    app = web.Application()
    app.router.add_post("/ws/auth/token", token_handler)
    app.router.add_get("/ws/data/file/JSON/user/1", data_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", PORT)
    await site.start()
    try:
        monkeypatch.setattr(canopy_adapter_hobolink, "TOKEN_URL", f"http://127.0.0.1:{PORT}/ws/auth/token")
        monkeypatch.setattr(canopy_adapter_hobolink, "API_BASE", f"http://127.0.0.1:{PORT}/ws")
        adapter = HobolinkAdapter()
        values = await adapter.read(make_room(user_id="1", logger_sn="20958060", fields={"temp_f": "Temperature"}))

        assert values == {"temp_f": 21.5}
        assert token_requests[0] == {"grant_type": "client_credentials", "client_id": "client-abc", "client_secret": "secret-xyz"}
        assert data_requests[0]["headers"]["Authorization"] == "Bearer tok-123"
        assert data_requests[0]["query"]["loggers"] == "20958060"
    finally:
        await runner.cleanup()


async def test_token_is_cached_across_reads(monkeypatch):
    set_env(monkeypatch)
    token_calls = []

    async def token_handler(request):
        token_calls.append(1)
        return web.json_response({"access_token": "tok-123", "expires_in": 3600})

    async def data_handler(request):
        return web.json_response({"series": [{"sensor_measurement_type": "Temperature", "readings": [{"value": 21.5}]}]})

    app = web.Application()
    app.router.add_post("/ws/auth/token", token_handler)
    app.router.add_get("/ws/data/file/JSON/user/1", data_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", PORT)
    await site.start()
    try:
        monkeypatch.setattr(canopy_adapter_hobolink, "TOKEN_URL", f"http://127.0.0.1:{PORT}/ws/auth/token")
        monkeypatch.setattr(canopy_adapter_hobolink, "API_BASE", f"http://127.0.0.1:{PORT}/ws")
        adapter = HobolinkAdapter()
        room = make_room(user_id="1", logger_sn="20958060", fields={"temp_f": "Temperature"})
        await adapter.read(room)
        await adapter.read(room)

        assert len(token_calls) == 1
    finally:
        await runner.cleanup()
