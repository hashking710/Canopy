import pytest
from canopy_adapter_trolmaster import TrolMasterCloudAdapter
from canopy_agent.models import Room


def make_room(**adapter_config) -> Room:
    return Room(
        id="trolmaster-room", room_type="greenhouse", path="~/trolmaster-room",
        adapter_type="trolmaster_cloud", metric_config={}, adapter_config=adapter_config,
    )


def test_plugin_metadata_is_set():
    assert "not yet functional" in TrolMasterCloudAdapter.plugin_name
    assert "device_id" in TrolMasterCloudAdapter.config_schema


async def test_read_raises_not_implemented_rather_than_pretending_to_work():
    adapter = TrolMasterCloudAdapter()
    with pytest.raises(NotImplementedError, match="blocked on real API Gateway access"):
        await adapter.read(make_room(device_id="123"))
