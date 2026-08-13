from datetime import datetime, timezone

import pytest
from aiohttp import web
import canopy_adapter_emporia_vue
from canopy_adapter_emporia_vue import (
    EmporiaVueAdapter,
    _format_instant,
    extract_channel_watts,
)
from canopy_agent.models import Room


def make_room(**adapter_config) -> Room:
    return Room(
        id="emporia-room", room_type="greenhouse", path="~/emporia-room",
        adapter_type="emporia_vue", metric_config={}, adapter_config=adapter_config,
    )


# ---- extract_channel_watts — pure, real response shape (see module docstring) -------


def test_extract_channel_watts_matches_device_and_channel():
    response = {
        "deviceListUsages": {
            "instant": "2026-01-01T00:00:00Z",
            "devices": [
                {"deviceGid": 555, "channelUsages": [
                    {"channelNum": "1,2,3", "usage": 0.001, "name": "Main"},
                    {"channelNum": "5", "usage": 0.0002, "name": "Grow Room"},
                ]},
            ],
        }
    }
    watts = extract_channel_watts(response, "555", "1,2,3")
    assert watts == pytest.approx(0.001 * 3600 * 1000)


def test_extract_channel_watts_picks_the_right_channel_not_just_the_first():
    response = {
        "deviceListUsages": {
            "devices": [
                {"deviceGid": 555, "channelUsages": [
                    {"channelNum": "1,2,3", "usage": 0.001},
                    {"channelNum": "5", "usage": 0.0002},
                ]},
            ],
        }
    }
    watts = extract_channel_watts(response, "555", "5")
    assert watts == pytest.approx(0.0002 * 3600 * 1000)


def test_extract_channel_watts_returns_none_for_unknown_channel():
    response = {
        "deviceListUsages": {
            "devices": [{"deviceGid": 555, "channelUsages": [{"channelNum": "1,2,3", "usage": 0.001}]}],
        }
    }
    assert extract_channel_watts(response, "555", "99") is None


def test_extract_channel_watts_returns_none_for_unknown_device():
    response = {"deviceListUsages": {"devices": [{"deviceGid": 555, "channelUsages": []}]}}
    assert extract_channel_watts(response, "999", "1,2,3") is None


def test_extract_channel_watts_handles_missing_top_level_key():
    assert extract_channel_watts({}, "555", "1,2,3") is None


def test_extract_channel_watts_skips_null_channel_entries():
    # Real API responses can include null entries in channelUsages — matches
    # PyEmVue's own defensive "if channel:" check in device.py.
    response = {
        "deviceListUsages": {
            "devices": [{"deviceGid": 555, "channelUsages": [None, {"channelNum": "1,2,3", "usage": 0.001}]}],
        }
    }
    watts = extract_channel_watts(response, "555", "1,2,3")
    assert watts == pytest.approx(0.001 * 3600 * 1000)


def test_extract_channel_watts_returns_none_when_usage_field_missing():
    response = {
        "deviceListUsages": {
            "devices": [{"deviceGid": 555, "channelUsages": [{"channelNum": "1,2,3"}]}],
        }
    }
    assert extract_channel_watts(response, "555", "1,2,3") is None


# ---- _format_instant — matches PyEmVue's own pyemvue.py:_format_time exactly --------


def test_format_instant_is_z_suffixed_isoformat_with_no_explicit_offset():
    moment = datetime(2026, 3, 5, 12, 30, 45, 123456, tzinfo=timezone.utc)
    result = _format_instant(moment)
    assert result == "2026-03-05T12:30:45.123456Z"
    assert "+" not in result


# ---- config validation ----------------------------------------------------------------


async def test_read_without_device_gid_raises(monkeypatch):
    monkeypatch.setenv("CANOPY_EMPORIA_EMAIL", "grower@example.com")
    monkeypatch.setenv("CANOPY_EMPORIA_PASSWORD", "secret")
    adapter = EmporiaVueAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.device_gid"):
        await adapter.read(make_room(channel_num="1,2,3"))


async def test_read_without_channel_num_raises(monkeypatch):
    monkeypatch.setenv("CANOPY_EMPORIA_EMAIL", "grower@example.com")
    monkeypatch.setenv("CANOPY_EMPORIA_PASSWORD", "secret")
    adapter = EmporiaVueAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.channel_num"):
        await adapter.read(make_room(device_gid="555"))


async def test_read_without_credentials_raises(monkeypatch):
    monkeypatch.delenv("CANOPY_EMPORIA_EMAIL", raising=False)
    monkeypatch.delenv("CANOPY_EMPORIA_PASSWORD", raising=False)
    adapter = EmporiaVueAdapter()
    with pytest.raises(RuntimeError, match="CANOPY_EMPORIA_EMAIL"):
        await adapter.read(make_room(device_gid="555", channel_num="1,2,3"))


def test_plugin_metadata_is_set():
    assert EmporiaVueAdapter.plugin_name == "Emporia Vue (whole-panel power monitoring)"
    assert "device_gid" in EmporiaVueAdapter.config_schema
    assert "channel_num" in EmporiaVueAdapter.config_schema
    assert "CANOPY_EMPORIA_EMAIL" in EmporiaVueAdapter.required_env_vars
    assert "CANOPY_EMPORIA_PASSWORD" in EmporiaVueAdapter.required_env_vars
    assert set(EmporiaVueAdapter.default_metric_config) == {"power_w"}
    assert EmporiaVueAdapter.supports_discovery is False


# ---- credential hot-reload — _login is mocked (real login goes through pycognito's
# real AWS Cognito SRP handshake, which can't be faked with a local test server the
# way a plain REST login can) --------------------------------------------------------


async def test_credential_change_forces_a_real_relogin_not_a_stale_session(monkeypatch):
    """Same hot-reload guarantee as canopy-adapter-ac-infinity's
    _logged_in_with: a login cached under one password must not silently keep being
    used once the dashboard (routers/secrets.py) has set a different one."""
    login_calls = []

    async def fake_login(self, email, password):
        login_calls.append((email, password))
        self._id_token = f"token-{len(login_calls)}"
        self._logged_in_with = (email, password)

    monkeypatch.setattr(EmporiaVueAdapter, "_login", fake_login)

    adapter = EmporiaVueAdapter()
    await adapter._ensure_logged_in("grower@example.com", "old-password")
    await adapter._ensure_logged_in("grower@example.com", "old-password")  # cached, no relogin
    await adapter._ensure_logged_in("grower@example.com", "new-password")  # changed -> relogin

    assert login_calls == [
        ("grower@example.com", "old-password"),
        ("grower@example.com", "new-password"),
    ]


# ---- real end-to-end read against a real local HTTP server, matching the wire shape
# read directly from PyEmVue's own source — the strongest verification available
# without a real Emporia Vue account and device. ---------------------------------


async def test_read_from_a_real_server_including_401_relogin_retry(monkeypatch):
    request_count = {"n": 0}

    async def usage_handler(request):
        request_count["n"] += 1
        assert request.query["deviceGids"] == "555"
        assert request.query["scale"] == "1S"
        assert request.query["energyUnit"] == "KilowattHours"
        if request_count["n"] == 1:
            return web.Response(status=401)  # simulates an expired/invalid id_token
        return web.json_response({
            "deviceListUsages": {
                "instant": "2026-01-01T00:00:00Z",
                "devices": [{"deviceGid": 555, "channelUsages": [{"channelNum": "1,2,3", "usage": 0.0005}]}],
            }
        })

    app = web.Application()
    app.router.add_get("/AppAPI", usage_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 18601)
    await site.start()
    try:
        monkeypatch.setattr(canopy_adapter_emporia_vue, "API_ROOT", "http://127.0.0.1:18601")

        login_calls = []

        async def fake_login(self, email, password):
            login_calls.append((email, password))
            self._id_token = f"token-{len(login_calls)}"
            self._logged_in_with = (email, password)

        monkeypatch.setattr(EmporiaVueAdapter, "_login", fake_login)
        monkeypatch.setenv("CANOPY_EMPORIA_EMAIL", "grower@example.com")
        monkeypatch.setenv("CANOPY_EMPORIA_PASSWORD", "secret")

        adapter = EmporiaVueAdapter()
        reading = await adapter.read(make_room(device_gid="555", channel_num="1,2,3"))

        assert reading == {"power_w": pytest.approx(0.0005 * 3600 * 1000)}
        assert request_count["n"] == 2  # first 401, retried once after a fresh login
        assert len(login_calls) == 2  # initial login + the forced relogin after 401
    finally:
        await runner.cleanup()


async def test_read_raises_on_a_persistent_non_200(monkeypatch):
    async def usage_handler(request):
        return web.Response(status=500)

    app = web.Application()
    app.router.add_get("/AppAPI", usage_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 18602)
    await site.start()
    try:
        monkeypatch.setattr(canopy_adapter_emporia_vue, "API_ROOT", "http://127.0.0.1:18602")

        async def fake_login(self, email, password):
            self._id_token = "token"
            self._logged_in_with = (email, password)

        monkeypatch.setattr(EmporiaVueAdapter, "_login", fake_login)
        monkeypatch.setenv("CANOPY_EMPORIA_EMAIL", "grower@example.com")
        monkeypatch.setenv("CANOPY_EMPORIA_PASSWORD", "secret")

        adapter = EmporiaVueAdapter()
        with pytest.raises(RuntimeError, match="HTTP 500"):
            await adapter.read(make_room(device_gid="555", channel_num="1,2,3"))
    finally:
        await runner.cleanup()
