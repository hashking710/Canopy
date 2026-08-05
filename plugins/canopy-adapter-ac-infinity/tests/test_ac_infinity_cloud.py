import pytest
from aiohttp import web
import canopy_adapter_ac_infinity
from canopy_adapter_ac_infinity import ACInfinityCloudAdapter
from canopy_agent.models import Room


def make_room(**adapter_config) -> Room:
    return Room(
        id="ac-room",
        room_type="greenhouse",
        path="~/ac-room",
        adapter_type="ac_infinity_cloud",
        metric_config={},
        adapter_config=adapter_config,
    )


async def test_read_without_credentials_raises(monkeypatch):
    monkeypatch.delenv("CANOPY_AC_INFINITY_EMAIL", raising=False)
    monkeypatch.delenv("CANOPY_AC_INFINITY_PASSWORD", raising=False)
    adapter = ACInfinityCloudAdapter()
    with pytest.raises(RuntimeError, match="CANOPY_AC_INFINITY_EMAIL"):
        await adapter.read(make_room(dev_id="123"))


async def test_read_without_dev_id_raises(monkeypatch):
    monkeypatch.setenv("CANOPY_AC_INFINITY_EMAIL", "grower@example.com")
    monkeypatch.setenv("CANOPY_AC_INFINITY_PASSWORD", "secret")
    adapter = ACInfinityCloudAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.dev_id"):
        await adapter.read(make_room())


async def test_credential_change_forces_a_real_relogin_not_a_stale_session(monkeypatch):
    """Login sessions are cached per adapter instance (see _ensure_controllers_fresh)
    for efficiency — but that cache must not silently keep using a session
    authenticated under a password the dashboard (routers/secrets.py) has since
    changed. Two logins, two different passwords, on the *same* adapter instance."""
    received_logins = []

    async def login_handler(request):
        body = await request.post()
        received_logins.append(body.get("appPasswordl"))
        return web.json_response({"code": 200, "data": {"appId": "user-1"}})

    async def device_list_handler(request):
        return web.json_response({"code": 200, "data": []})

    app = web.Application()
    app.router.add_post("/api/user/appUserLogin", login_handler)
    app.router.add_post("/api/user/devInfoListAll", device_list_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 18401)
    await site.start()
    try:
        monkeypatch.setattr(canopy_adapter_ac_infinity, "HOST", "http://127.0.0.1:18401")
        monkeypatch.setattr(canopy_adapter_ac_infinity, "CONTROLLER_CACHE_SECONDS", 0)
        adapter = ACInfinityCloudAdapter()  # one instance, reused across both reads below

        monkeypatch.setenv("CANOPY_AC_INFINITY_EMAIL", "grower@example.com")
        monkeypatch.setenv("CANOPY_AC_INFINITY_PASSWORD", "old-password")
        with pytest.raises(RuntimeError, match="no controller"):
            await adapter.read(make_room(dev_id="missing"))

        monkeypatch.setenv("CANOPY_AC_INFINITY_PASSWORD", "new-password")  # simulates PUT /api/secrets
        with pytest.raises(RuntimeError, match="no controller"):
            await adapter.read(make_room(dev_id="missing"))

        assert received_logins == ["old-password", "new-password"]
    finally:
        await runner.cleanup()


def test_plugin_metadata_is_set():
    assert ACInfinityCloudAdapter.plugin_name == "AC Infinity (Cloud/WiFi)"
    assert "dev_id" in ACInfinityCloudAdapter.config_schema
    assert "CANOPY_AC_INFINITY_EMAIL" in ACInfinityCloudAdapter.required_env_vars
    assert "CANOPY_AC_INFINITY_PASSWORD" in ACInfinityCloudAdapter.required_env_vars
    assert set(ACInfinityCloudAdapter.default_metric_config) == {"temp_f", "rh_pct", "vpd_kpa"}
