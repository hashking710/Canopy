import pytest
from canopy_adapter_argus import ArgusAdapter
from canopy_agent.models import Room


def make_room(**adapter_config) -> Room:
    return Room(
        id="argus-room", room_type="greenhouse", path="~/argus-room",
        adapter_type="argus", metric_config={}, adapter_config=adapter_config,
    )


def test_plugin_metadata_is_set():
    assert ArgusAdapter.plugin_name == "Argus Controls (Titan/Axia)"
    assert ArgusAdapter.category == "local"
    assert "host" in ArgusAdapter.config_schema


async def test_read_without_host_raises():
    adapter = ArgusAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.host"):
        await adapter.read(make_room(username="u", password="p"))


async def test_read_without_credentials_raises():
    adapter = ArgusAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.username and adapter_config.password"):
        await adapter.read(make_room(host="192.168.1.50"))


async def test_read_raises_not_implemented_rather_than_pretending_to_work():
    adapter = ArgusAdapter()
    with pytest.raises(NotImplementedError, match="no publicly published endpoint reference"):
        await adapter.read(make_room(host="192.168.1.50", username="u", password="p"))
