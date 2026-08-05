import pytest
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


def test_plugin_metadata_is_set():
    assert ACInfinityCloudAdapter.plugin_name == "AC Infinity (Cloud/WiFi)"
    assert "dev_id" in ACInfinityCloudAdapter.config_schema
    assert "CANOPY_AC_INFINITY_EMAIL" in ACInfinityCloudAdapter.required_env_vars
    assert "CANOPY_AC_INFINITY_PASSWORD" in ACInfinityCloudAdapter.required_env_vars
    assert set(ACInfinityCloudAdapter.default_metric_config) == {"temp_f", "rh_pct", "vpd_kpa"}
