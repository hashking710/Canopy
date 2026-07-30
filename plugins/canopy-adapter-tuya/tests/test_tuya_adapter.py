import pytest
from canopy_adapter_tuya import TuyaAdapter, extract_tuya_metrics
from canopy_agent.models import Room


def make_room(**adapter_config) -> Room:
    return Room(
        id="tuya-room", room_type="greenhouse", path="~/tuya-room",
        adapter_type="tuya", metric_config={}, adapter_config=adapter_config,
    )


# ---- DP extraction — pure, real tinytuya-shaped response, no device involved --------


def test_extract_tuya_metrics_known_dps():
    status = {"dps": {"1": True, "5": 45, "19": 235}}
    values = extract_tuya_metrics(status, {"soil_pct": "5", "temp_raw": "19"})
    assert values == {"soil_pct": 45.0, "temp_raw": 235.0}


def test_extract_tuya_metrics_missing_dp_raises():
    status = {"dps": {"1": True}}
    with pytest.raises(RuntimeError, match="no data point '5'"):
        extract_tuya_metrics(status, {"soil_pct": "5"})


def test_extract_tuya_metrics_non_numeric_dp_raises():
    status = {"dps": {"5": "not a number"}}
    with pytest.raises(RuntimeError, match="not numeric"):
        extract_tuya_metrics(status, {"soil_pct": "5"})


def test_extract_tuya_metrics_empty_dps():
    assert extract_tuya_metrics({"dps": {}}, {}) == {}


# ---- config validation ----------------------------------------------------------------


async def test_read_without_required_fields_raises():
    adapter = TuyaAdapter()
    with pytest.raises(RuntimeError, match="needs adapter_config"):
        await adapter.read(make_room())


async def test_read_without_dps_raises():
    adapter = TuyaAdapter()
    room = make_room(device_id="abc", local_key="key", ip="192.168.1.50")
    with pytest.raises(RuntimeError, match="adapter_config.dps"):
        await adapter.read(room)


def test_plugin_metadata_is_set():
    assert TuyaAdapter.plugin_name == "Tuya (local protocol)"
    assert "local_key" in TuyaAdapter.config_schema
