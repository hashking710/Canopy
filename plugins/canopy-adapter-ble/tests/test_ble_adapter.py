import struct

import pytest
from canopy_adapter_ble import BleAdapter, BleAdvertisementAdapter, decode_ble_value
from canopy_agent.models import Room


def make_room(**adapter_config) -> Room:
    return Room(
        id="ble-room", room_type="greenhouse", path="~/ble-room",
        adapter_type="ble", metric_config={}, adapter_config=adapter_config,
    )


# ---- byte-format decoding — pure, no BLE connection involved ------------------------


def test_decode_ble_value_sint16_sig_environmental_temperature():
    # Bluetooth SIG's 0x2A6E Temperature characteristic: sint16, 0.01C units.
    raw = struct.pack("<h", 2350)  # 23.50C
    value = decode_ble_value(raw, {"format": "sint16_le", "scale": 0.01})
    assert value == pytest.approx(23.50)


def test_decode_ble_value_applies_c_to_f():
    raw = struct.pack("<h", 2500)  # 25.00C
    value = decode_ble_value(raw, {"format": "sint16_le", "scale": 0.01, "c_to_f": True})
    assert value == pytest.approx(25.0 * 9 / 5 + 32)


def test_decode_ble_value_uint8():
    raw = struct.pack("<B", 55)
    assert decode_ble_value(raw, {"format": "uint8"}) == 55.0


def test_decode_ble_value_sint8_negative():
    raw = struct.pack("<b", -20)
    assert decode_ble_value(raw, {"format": "sint8"}) == -20.0


def test_decode_ble_value_uint32():
    raw = struct.pack("<I", 123456)
    assert decode_ble_value(raw, {"format": "uint32_le"}) == 123456.0


def test_decode_ble_value_float32():
    raw = struct.pack("<f", 12.34)
    assert decode_ble_value(raw, {"format": "float32_le"}) == pytest.approx(12.34, abs=1e-4)


def test_decode_ble_value_default_format_is_float32():
    raw = struct.pack("<f", 5.5)
    assert decode_ble_value(raw, {}) == pytest.approx(5.5)


def test_decode_ble_value_applies_offset():
    raw = struct.pack("<B", 10)
    assert decode_ble_value(raw, {"format": "uint8", "scale": 2.0, "offset": 1.0}) == 21.0


def test_decode_ble_value_unknown_format_raises():
    with pytest.raises(RuntimeError, match="unknown format"):
        decode_ble_value(b"\x00\x00", {"format": "carrier-pigeon"})


def test_decode_ble_value_too_few_bytes_raises():
    with pytest.raises(RuntimeError, match="need at least"):
        decode_ble_value(b"\x00", {"format": "uint32_le"})


def test_decode_ble_value_extra_bytes_are_ignored():
    # Some real devices pad characteristics with trailing bytes beyond the value —
    # only the leading bytes needed for the declared format should be consumed.
    raw = struct.pack("<B", 42) + b"\xff\xff\xff"
    assert decode_ble_value(raw, {"format": "uint8"}) == 42.0


# ---- config validation ----------------------------------------------------------------


async def test_read_without_address_raises():
    adapter = BleAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.address"):
        await adapter.read(make_room())


async def test_read_without_characteristics_raises():
    adapter = BleAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.characteristics"):
        await adapter.read(make_room(address="AA:BB:CC:DD:EE:FF"))


def test_plugin_metadata_is_set():
    assert BleAdapter.plugin_name == "BLE (generic GATT characteristic)"
    assert "address" in BleAdapter.config_schema


# ---- BleAdvertisementAdapter — config validation, byte-offset slicing reuses the
# same decode_ble_value already tested above ------------------------------------------


async def test_advertisement_read_without_address_raises():
    adapter = BleAdvertisementAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.address"):
        await adapter.read(make_room())


async def test_advertisement_read_without_service_data_uuid_raises():
    adapter = BleAdvertisementAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.service_data_uuid"):
        await adapter.read(make_room(address="AA:BB:CC:DD:EE:FF"))


async def test_advertisement_read_without_fields_raises():
    adapter = BleAdvertisementAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.fields"):
        await adapter.read(
            make_room(address="AA:BB:CC:DD:EE:FF", service_data_uuid="0000181a-0000-1000-8000-00805f9b34fb")
        )


def test_advertisement_plugin_metadata_is_set():
    assert BleAdvertisementAdapter.plugin_name == "BLE (passive advertisement scan)"
    assert "service_data_uuid" in BleAdvertisementAdapter.config_schema


def test_advertisement_field_decode_reuses_decode_ble_value_with_byte_offset():
    # Simulates what read() does after scanning: slice the payload at byte_offset,
    # then decode — the Xiaomi-style layout this adapter is meant to cover (MAC(6) +
    # temp(2) + humidity(1) + ...).
    payload = bytes(6) + struct.pack("<h", 2200) + struct.pack("<B", 48)  # temp=22.00C, humidity=48%
    temp = decode_ble_value(payload[6:], {"format": "sint16_le", "scale": 0.01, "c_to_f": True})
    humidity = decode_ble_value(payload[8:], {"format": "uint8"})
    assert temp == pytest.approx(22.0 * 9 / 5 + 32)
    assert humidity == 48.0
