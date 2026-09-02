import pytest
from canopy_adapter_growlink import GrowlinkAdapter
from canopy_agent.models import Room


def make_room(**adapter_config) -> Room:
    return Room(
        id="growlink-room", room_type="greenhouse", path="~/growlink-room",
        adapter_type="growlink", metric_config={}, adapter_config=adapter_config,
    )


def test_plugin_metadata_is_set():
    assert GrowlinkAdapter.plugin_name == "Growlink"
    assert "device_id" in GrowlinkAdapter.config_schema
    assert "CANOPY_GROWLINK_API_KEY" in GrowlinkAdapter.required_env_vars


async def test_read_without_api_key_raises(monkeypatch):
    monkeypatch.delenv("CANOPY_GROWLINK_API_KEY", raising=False)
    adapter = GrowlinkAdapter()
    with pytest.raises(RuntimeError, match="CANOPY_GROWLINK_API_KEY"):
        await adapter.read(make_room(device_id="123"))


async def test_read_without_device_id_raises(monkeypatch):
    monkeypatch.setenv("CANOPY_GROWLINK_API_KEY", "key")
    adapter = GrowlinkAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.device_id"):
        await adapter.read(make_room())


async def test_read_raises_not_implemented_rather_than_pretending_to_work(monkeypatch):
    monkeypatch.setenv("CANOPY_GROWLINK_API_KEY", "key")
    adapter = GrowlinkAdapter()
    with pytest.raises(NotImplementedError, match="developer-account signup"):
        await adapter.read(make_room(device_id="123"))
