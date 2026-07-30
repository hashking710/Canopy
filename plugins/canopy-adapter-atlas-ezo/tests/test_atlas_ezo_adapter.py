import pytest
from canopy_adapter_atlas_ezo import AtlasEzoAdapter, _extract_ec_field, parse_ezo_response
from canopy_agent.models import Room


def make_room(**adapter_config) -> Room:
    return Room(
        id="ezo-room", room_type="greenhouse", path="~/ezo-room",
        adapter_type="atlas_ezo", metric_config={}, adapter_config=adapter_config,
    )


# ---- response parsing — pure, no I2C bus involved ------------------------------------


def test_parse_ezo_response_success_single_value():
    # status byte 1 = success, then null-terminated ASCII "7.00"
    raw = bytes([1]) + b"7.00" + bytes([0]) * 10
    assert parse_ezo_response(raw) == "7.00"


def test_parse_ezo_response_success_no_null_terminator():
    # Some real devices fill the buffer exactly with no trailing null.
    raw = bytes([1]) + b"1413.00"
    assert parse_ezo_response(raw) == "1413.00"


def test_parse_ezo_response_syntax_error_raises():
    with pytest.raises(RuntimeError, match="syntax error"):
        parse_ezo_response(bytes([2]) + bytes(31))


def test_parse_ezo_response_still_processing_raises():
    with pytest.raises(RuntimeError, match="still processing"):
        parse_ezo_response(bytes([254]) + bytes(31))


def test_parse_ezo_response_no_data_raises():
    with pytest.raises(RuntimeError, match="no data"):
        parse_ezo_response(bytes([255]) + bytes(31))


def test_parse_ezo_response_unknown_status_raises():
    with pytest.raises(RuntimeError, match="unrecognized status"):
        parse_ezo_response(bytes([99]) + bytes(31))


def test_parse_ezo_response_empty_raises():
    with pytest.raises(RuntimeError, match="empty response"):
        parse_ezo_response(b"")


# ---- EC multi-field extraction — pure ------------------------------------------------


def test_extract_ec_field_default_first_field():
    assert _extract_ec_field("1413.00,706,0.68,1.00", 0) == 1413.00


def test_extract_ec_field_tds():
    assert _extract_ec_field("1413.00,706,0.68,1.00", 1) == 706.0


def test_extract_ec_field_single_value_response():
    assert _extract_ec_field("1413.00", 0) == 1413.00


def test_extract_ec_field_out_of_range_raises():
    with pytest.raises(RuntimeError, match="no field at index"):
        _extract_ec_field("1413.00", 5)


def test_extract_ec_field_non_numeric_raises():
    with pytest.raises(RuntimeError, match="not numeric"):
        _extract_ec_field("error,706", 0)


# ---- config validation ----------------------------------------------------------------


async def test_read_without_sensors_raises():
    adapter = AtlasEzoAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.sensors"):
        await adapter.read(make_room())


async def test_read_with_unknown_kind_raises():
    adapter = AtlasEzoAdapter()
    sensors = [{"metric": "x", "kind": "unobtainium", "i2c_bus": 1, "i2c_address": "0x63"}]
    with pytest.raises(RuntimeError, match="unknown EZO probe kind"):
        await adapter.read(make_room(sensors=sensors))


async def test_read_without_metric_raises():
    adapter = AtlasEzoAdapter()
    sensors = [{"kind": "ph", "i2c_bus": 1, "i2c_address": "0x63"}]
    with pytest.raises(RuntimeError, match="missing 'metric'"):
        await adapter.read(make_room(sensors=sensors))


def test_plugin_metadata_is_set():
    assert AtlasEzoAdapter.plugin_name == "Atlas Scientific EZO (I2C)"
    assert "sensors" in AtlasEzoAdapter.config_schema
