import base64
import hashlib
import hmac

import pytest
from aiohttp import web
import canopy_adapter_switchbot
from canopy_adapter_switchbot import SwitchBotAdapter, _parse_status, sign_headers
from canopy_agent.models import Room


def make_room(**adapter_config) -> Room:
    return Room(
        id="switchbot-room", room_type="greenhouse", path="~/switchbot-room",
        adapter_type="switchbot", metric_config={}, adapter_config=adapter_config,
    )


# ---- request signing — pure, no network involved -----------------------------------


def test_sign_headers_produces_a_verifiable_hmac():
    headers = sign_headers("test-token", "test-secret")
    # Recompute the signature independently (not by calling sign_headers again) to
    # prove the recipe itself is right, not just that the function is deterministic.
    string_to_sign = f"test-token{headers['t']}{headers['nonce']}"
    expected = base64.b64encode(
        hmac.new(b"test-secret", string_to_sign.encode(), hashlib.sha256).digest()
    ).decode()
    assert headers["sign"] == expected
    assert headers["Authorization"] == "test-token"


def test_sign_headers_uses_a_fresh_nonce_each_call():
    first = sign_headers("token", "secret")
    second = sign_headers("token", "secret")
    assert first["nonce"] != second["nonce"]


# ---- response parsing — pure, no network involved -----------------------------------


def test_parse_status_meter_reports_temp_and_humidity():
    body = {"deviceId": "ABC", "deviceType": "Meter", "temperature": 26.1, "humidity": 52}
    values = _parse_status(body)
    assert values["temp_f"] == pytest.approx(26.1 * 9 / 5 + 32)
    assert values["rh_pct"] == 52.0


def test_parse_status_device_with_neither_field_returns_empty():
    assert _parse_status({"deviceId": "ABC", "deviceType": "Plug"}) == {}


# ---- config validation ----------------------------------------------------------------


async def test_read_without_credentials_raises(monkeypatch):
    monkeypatch.delenv("CANOPY_SWITCHBOT_TOKEN", raising=False)
    monkeypatch.delenv("CANOPY_SWITCHBOT_SECRET", raising=False)
    adapter = SwitchBotAdapter()
    with pytest.raises(RuntimeError, match="CANOPY_SWITCHBOT_TOKEN"):
        await adapter.read(make_room(device_id="ABC"))


async def test_read_without_device_id_raises(monkeypatch):
    monkeypatch.setenv("CANOPY_SWITCHBOT_TOKEN", "t")
    monkeypatch.setenv("CANOPY_SWITCHBOT_SECRET", "s")
    adapter = SwitchBotAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.device_id"):
        await adapter.read(make_room())


def test_plugin_metadata_is_set():
    assert SwitchBotAdapter.plugin_name == "SwitchBot (Cloud API)"
    assert "device_id" in SwitchBotAdapter.config_schema
    assert "CANOPY_SWITCHBOT_TOKEN" in SwitchBotAdapter.required_env_vars
    assert "CANOPY_SWITCHBOT_SECRET" in SwitchBotAdapter.required_env_vars
    assert set(SwitchBotAdapter.default_metric_config) == {"temp_f", "rh_pct"}


# ---- real end-to-end read against a real local HTTP server, verifying both the
# request (correctly signed) and the response parsing — API_BASE is monkeypatched to
# a local server since the real API only lives at api.switch-bot.com, but everything
# else in the request/response path is exercised for real. ---------------------------


async def test_read_from_a_real_server_with_real_signing(monkeypatch):
    monkeypatch.setenv("CANOPY_SWITCHBOT_TOKEN", "test-token")
    monkeypatch.setenv("CANOPY_SWITCHBOT_SECRET", "test-secret")
    received_headers = {}

    async def handler(request):
        received_headers.update(request.headers)
        return web.json_response(
            {
                "statusCode": 100,
                "body": {"deviceId": "ABC", "deviceType": "Meter", "temperature": 22.0, "humidity": 60},
                "message": "success",
            }
        )

    app = web.Application()
    app.router.add_get("/v1.1/devices/ABC/status", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 18201)
    await site.start()
    try:
        monkeypatch.setattr(canopy_adapter_switchbot, "API_BASE", "http://127.0.0.1:18201/v1.1")
        adapter = SwitchBotAdapter()
        values = await adapter.read(make_room(device_id="ABC"))

        assert values["temp_f"] == pytest.approx(22.0 * 9 / 5 + 32)
        assert values["rh_pct"] == 60.0
        # The request the server actually received was really signed, not just a
        # bare Authorization header.
        assert received_headers["Authorization"] == "test-token"
        assert "sign" in received_headers
        assert "nonce" in received_headers
    finally:
        await runner.cleanup()


async def test_credential_change_takes_effect_on_the_next_read_without_recreating_the_adapter(monkeypatch):
    """The whole point of reading os.environ inside read() instead of caching it in
    __init__: a credential set through the dashboard (routers/secrets.py) must take
    effect on the very next poll cycle on the *same*, already-constructed adapter
    instance (adapters/registry.py caches one instance per adapter_type)."""
    received_tokens = []

    async def handler(request):
        received_tokens.append(request.headers.get("Authorization"))
        return web.json_response({"statusCode": 100, "body": {}, "message": "success"})

    app = web.Application()
    app.router.add_get("/v1.1/devices/ABC/status", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 18202)
    await site.start()
    try:
        monkeypatch.setattr(canopy_adapter_switchbot, "API_BASE", "http://127.0.0.1:18202/v1.1")
        adapter = SwitchBotAdapter()  # one instance, reused across both reads below

        monkeypatch.setenv("CANOPY_SWITCHBOT_TOKEN", "old-token")
        monkeypatch.setenv("CANOPY_SWITCHBOT_SECRET", "old-secret")
        await adapter.read(make_room(device_id="ABC"))

        monkeypatch.setenv("CANOPY_SWITCHBOT_TOKEN", "new-token")  # simulates PUT /api/secrets
        await adapter.read(make_room(device_id="ABC"))

        assert received_tokens == ["old-token", "new-token"]
    finally:
        await runner.cleanup()


async def test_error_status_code_raises(monkeypatch):
    monkeypatch.setenv("CANOPY_SWITCHBOT_TOKEN", "t")
    monkeypatch.setenv("CANOPY_SWITCHBOT_SECRET", "s")

    async def handler(request):
        return web.json_response({"statusCode": 190, "message": "Device not found", "body": {}})

    app = web.Application()
    app.router.add_get("/v1.1/devices/BAD/status", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 18202)
    await site.start()
    try:
        monkeypatch.setattr(canopy_adapter_switchbot, "API_BASE", "http://127.0.0.1:18202/v1.1")
        adapter = SwitchBotAdapter()
        with pytest.raises(RuntimeError, match="Device not found"):
            await adapter.read(make_room(device_id="BAD"))
    finally:
        await runner.cleanup()
