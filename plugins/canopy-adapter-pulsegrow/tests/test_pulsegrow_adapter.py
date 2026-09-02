import pytest
from canopy_adapter_pulsegrow import PulseGrowAdapter
from canopy_agent.models import Room


def make_room(**adapter_config) -> Room:
    return Room(
        id="pulsegrow-room", room_type="greenhouse", path="~/pulsegrow-room",
        adapter_type="pulsegrow", metric_config={}, adapter_config=adapter_config,
    )


def test_plugin_metadata_is_set():
    assert PulseGrowAdapter.plugin_name == "Pulse Grow"
    assert "device_id" in PulseGrowAdapter.config_schema
    assert "CANOPY_PULSEGROW_API_KEY" in PulseGrowAdapter.required_env_vars


async def test_read_without_api_key_raises(monkeypatch):
    monkeypatch.delenv("CANOPY_PULSEGROW_API_KEY", raising=False)
    adapter = PulseGrowAdapter()
    with pytest.raises(RuntimeError, match="CANOPY_PULSEGROW_API_KEY"):
        await adapter.read(make_room(device_id="123"))


async def test_read_without_device_id_raises(monkeypatch):
    monkeypatch.setenv("CANOPY_PULSEGROW_API_KEY", "key")
    adapter = PulseGrowAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.device_id"):
        await adapter.read(make_room())


async def test_read_raises_not_implemented_rather_than_pretending_to_work(monkeypatch):
    monkeypatch.setenv("CANOPY_PULSEGROW_API_KEY", "key")
    adapter = PulseGrowAdapter()
    with pytest.raises(NotImplementedError, match="JavaScript"):
        await adapter.read(make_room(device_id="123"))
