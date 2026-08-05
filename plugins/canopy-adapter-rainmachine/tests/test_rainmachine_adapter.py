import pytest
from aiohttp import web
from canopy_adapter_rainmachine import RainMachineAdapter, is_zone_active
from canopy_agent.models import Room


def make_room(**adapter_config) -> Room:
    return Room(
        id="rainmachine-room", room_type="greenhouse", path="~/rainmachine-room",
        adapter_type="rainmachine", metric_config={}, adapter_config=adapter_config,
    )


# ---- zone-state check — pure, no network involved -----------------------------------


def test_is_zone_active_matching_zone_watering():
    assert is_zone_active([{"uid": 1, "state": 1}, {"uid": 2, "state": 0}], 1) is True


def test_is_zone_active_matching_zone_idle():
    assert is_zone_active([{"uid": 1, "state": 0}], 1) is False


def test_is_zone_active_zone_not_found():
    assert is_zone_active([{"uid": 2, "state": 1}], 1) is False


def test_is_zone_active_empty_zones():
    assert is_zone_active([], 1) is False


# ---- config validation ----------------------------------------------------------------


async def test_read_without_password_raises(monkeypatch):
    monkeypatch.delenv("CANOPY_RAINMACHINE_PASSWORD", raising=False)
    adapter = RainMachineAdapter()
    with pytest.raises(RuntimeError, match="CANOPY_RAINMACHINE_PASSWORD"):
        await adapter.read(make_room(host="http://127.0.0.1:1", zone_id=1))


async def test_read_without_host_or_zone_raises(monkeypatch):
    monkeypatch.setenv("CANOPY_RAINMACHINE_PASSWORD", "pw")
    adapter = RainMachineAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.host and adapter_config.zone_id"):
        await adapter.read(make_room())


def test_plugin_metadata_is_set():
    assert RainMachineAdapter.plugin_name == "RainMachine (local API)"
    assert "zone_id" in RainMachineAdapter.config_schema
    assert "CANOPY_RAINMACHINE_PASSWORD" in RainMachineAdapter.required_env_vars
    assert set(RainMachineAdapter.default_metric_config) == {"zone_active"}


# ---- real end-to-end read against a real local server — login + token + zone query --


async def test_read_performs_a_real_login_then_zone_query(monkeypatch):
    monkeypatch.setenv("CANOPY_RAINMACHINE_PASSWORD", "test-password")
    received_login_body = {}

    async def login_handler(request):
        received_login_body.update(await request.json())
        return web.json_response({"access_token": "real-token-123", "statusCode": 0})

    async def zone_handler(request):
        assert request.query["access_token"] == "real-token-123"
        return web.json_response({"zones": [{"uid": 1, "name": "Bed A", "state": 1}]})

    app = web.Application()
    app.router.add_post("/api/4/auth/login", login_handler)
    app.router.add_get("/api/4/zone", zone_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 18501)
    await site.start()
    try:
        adapter = RainMachineAdapter()
        room = make_room(host="http://127.0.0.1:18501", zone_id=1)
        values = await adapter.read(room)

        assert values == {"zone_active": 1.0}
        assert received_login_body == {"pwd": "test-password", "remember": True}
    finally:
        await runner.cleanup()


async def test_read_caches_the_token_across_reads(monkeypatch):
    monkeypatch.setenv("CANOPY_RAINMACHINE_PASSWORD", "test-password")
    login_call_count = {"n": 0}

    async def login_handler(request):
        login_call_count["n"] += 1
        return web.json_response({"access_token": "tok", "statusCode": 0})

    async def zone_handler(request):
        return web.json_response({"zones": [{"uid": 1, "state": 0}]})

    app = web.Application()
    app.router.add_post("/api/4/auth/login", login_handler)
    app.router.add_get("/api/4/zone", zone_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 18502)
    await site.start()
    try:
        adapter = RainMachineAdapter()
        room = make_room(host="http://127.0.0.1:18502", zone_id=1)
        await adapter.read(room)
        await adapter.read(room)
        assert login_call_count["n"] == 1
    finally:
        await runner.cleanup()


async def test_login_failure_raises_a_clear_error(monkeypatch):
    monkeypatch.setenv("CANOPY_RAINMACHINE_PASSWORD", "wrong-password")

    async def login_handler(request):
        return web.json_response({"statusCode": -1, "message": "bad password"}, status=401)

    app = web.Application()
    app.router.add_post("/api/4/auth/login", login_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 18503)
    await site.start()
    try:
        adapter = RainMachineAdapter()
        room = make_room(host="http://127.0.0.1:18503", zone_id=1)
        with pytest.raises(RuntimeError, match="login .* failed"):
            await adapter.read(room)
    finally:
        await runner.cleanup()
