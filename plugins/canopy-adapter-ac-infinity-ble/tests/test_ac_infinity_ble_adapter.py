import struct

import pytest
import canopy_adapter_ac_infinity_ble as aib
from canopy_adapter_ac_infinity_ble import (
    AcInfinityBleAdapter,
    _format_discovery_results,
    _get_bits,
    _reading_from_manufacturer_data,
    parse_ac_infinity_manufacturer_data,
)
from canopy_agent.models import Room


def make_room(**adapter_config) -> Room:
    return Room(
        id="ac-infinity-ble-room", room_type="greenhouse", path="~/ac-infinity-ble-room",
        adapter_type="ac_infinity_ble", metric_config={}, adapter_config=adapter_config,
    )


def _build_manufacturer_data(
    *, controller_type=7, version=3, temp_c=24.50, hum_pct=55.0, fan_level=5,
    vpd_kpa=None, flags_byte=0,
) -> bytes:
    """Constructs a real byte layout matching ac-infinity-ble's protocol.py
    (see module docstring for the exact field-by-field citation) so parsing can be
    round-tripped against known values without a real device."""
    data = bytearray(23)
    data[6:11] = b"ABCDE"
    data[11] = version
    data[12] = controller_type
    data[13] = flags_byte
    struct.pack_into(">h", data, 14, round(temp_c * 100))
    struct.pack_into(">h", data, 16, round(hum_pct * 100))
    data[18] = fan_level
    if vpd_kpa is not None:
        data[19] = 1  # choose_port
        data[20] = 0
        struct.pack_into(">h", data, 21, round(vpd_kpa * 100))
    else:
        data = data[:19]
    return bytes(data)


# ---- pure byte parsing — real, verified byte layout (see module docstring) ----------


def test_parse_decodes_temp_humidity_fan():
    data = _build_manufacturer_data(temp_c=24.50, hum_pct=55.0, fan_level=5)
    parsed = parse_ac_infinity_manufacturer_data(data)
    assert parsed["temp_c"] == pytest.approx(24.50)
    assert parsed["hum_pct"] == pytest.approx(55.0)
    assert parsed["fan_level"] == 5


def test_parse_handles_negative_temperature():
    data = _build_manufacturer_data(temp_c=-5.25, hum_pct=40.0, fan_level=0)
    parsed = parse_ac_infinity_manufacturer_data(data)
    assert parsed["temp_c"] == pytest.approx(-5.25)


def test_parse_includes_vpd_only_for_capable_controller_types():
    data = _build_manufacturer_data(controller_type=7, version=3, vpd_kpa=1.2)
    parsed = parse_ac_infinity_manufacturer_data(data)
    assert parsed["vpd_kpa"] == pytest.approx(1.2)


def test_parse_omits_vpd_for_non_capable_controller_type():
    data = _build_manufacturer_data(controller_type=2, version=3)
    parsed = parse_ac_infinity_manufacturer_data(data)
    assert "vpd_kpa" not in parsed


def test_parse_omits_vpd_for_old_firmware_version():
    data = _build_manufacturer_data(controller_type=7, version=2)
    parsed = parse_ac_infinity_manufacturer_data(data)
    assert "vpd_kpa" not in parsed


def test_parse_too_short_raises():
    with pytest.raises(RuntimeError, match="need at least"):
        parse_ac_infinity_manufacturer_data(bytes(5))


def test_get_bits_matches_manual_bit_extraction():
    # 0b10110100 -> 2 bits starting at position 2 (0-indexed from MSB) == 0b11 == 3
    assert _get_bits(0b10110100, 2, 2) == 0b11


# ---- reading conversion (C->F, VPD passthrough, fan level->percent) -----------------


def test_reading_converts_celsius_to_fahrenheit():
    data = _build_manufacturer_data(temp_c=24.50, hum_pct=55.0, fan_level=5)
    reading = _reading_from_manufacturer_data(data)
    assert reading["temp_f"] == pytest.approx(24.50 * 9 / 5 + 32)
    assert reading["rh_pct"] == pytest.approx(55.0)


def test_reading_maps_fan_level_zero_to_ten_scale_to_percent():
    data = _build_manufacturer_data(fan_level=7)
    reading = _reading_from_manufacturer_data(data)
    assert reading["fan_pct"] == 70.0


def test_reading_fan_off_is_zero_percent():
    data = _build_manufacturer_data(fan_level=0)
    reading = _reading_from_manufacturer_data(data)
    assert reading["fan_pct"] == 0.0


def test_reading_includes_vpd_when_present():
    data = _build_manufacturer_data(controller_type=7, version=3, vpd_kpa=1.35)
    reading = _reading_from_manufacturer_data(data)
    assert reading["vpd_kpa"] == pytest.approx(1.35)


def test_reading_omits_vpd_when_not_present():
    data = _build_manufacturer_data(controller_type=2, version=3)
    reading = _reading_from_manufacturer_data(data)
    assert "vpd_kpa" not in reading


# ---- config validation ----------------------------------------------------------------


async def test_read_without_address_raises():
    adapter = AcInfinityBleAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.address"):
        await adapter.read(make_room())


def test_plugin_metadata_is_set():
    assert AcInfinityBleAdapter.plugin_name == "AC Infinity (Bluetooth-only controllers)"
    assert "address" in AcInfinityBleAdapter.config_schema
    assert set(AcInfinityBleAdapter.default_metric_config) == {"temp_f", "rh_pct", "fan_pct"}
    assert AcInfinityBleAdapter.supports_discovery is True


# ---- discover() — mocks the live scan, same boundary as canopy-adapter-ble/shelly ---


def test_format_discovery_results_labels_by_controller_type():
    data = _build_manufacturer_data(controller_type=7)
    raw = {"AA:BB:CC:DD:EE:FF": data}
    results = _format_discovery_results(raw)
    assert results == [{"address": "AA:BB:CC:DD:EE:FF", "name": "AC Infinity controller (type 7)"}]


def test_format_discovery_results_skips_unparseable_payloads():
    raw = {"AA:BB:CC:DD:EE:FF": bytes(3)}  # too short
    assert _format_discovery_results(raw) == []


def test_format_discovery_results_sorted_by_address():
    raw = {
        "BB:BB:BB:BB:BB:BB": _build_manufacturer_data(controller_type=2),
        "AA:AA:AA:AA:AA:AA": _build_manufacturer_data(controller_type=3),
    }
    addresses = [r["address"] for r in _format_discovery_results(raw)]
    assert addresses == ["AA:AA:AA:AA:AA:AA", "BB:BB:BB:BB:BB:BB"]


async def test_discover_glues_the_scan_and_the_formatter(monkeypatch):
    async def fake_scan(timeout):
        return {"AA:BB:CC:DD:EE:FF": _build_manufacturer_data(controller_type=9)}

    monkeypatch.setattr(aib, "_scan_for_ac_infinity_advertisements", fake_scan)

    results = await AcInfinityBleAdapter.discover()
    assert results == [{"address": "AA:BB:CC:DD:EE:FF", "name": "AC Infinity controller (type 9)"}]


async def test_read_uses_the_scanned_payload_for_the_matching_address(monkeypatch):
    async def fake_scan(address, timeout):
        assert address == "AA:BB:CC:DD:EE:FF"
        return _build_manufacturer_data(temp_c=20.0, hum_pct=50.0, fan_level=3)

    monkeypatch.setattr(aib, "_scan_for_address", fake_scan)

    adapter = AcInfinityBleAdapter()
    reading = await adapter.read(make_room(address="AA:BB:CC:DD:EE:FF"))
    assert reading["temp_f"] == pytest.approx(20.0 * 9 / 5 + 32)
    assert reading["fan_pct"] == 30.0


async def test_read_raises_when_no_advertisement_seen(monkeypatch):
    async def fake_scan(address, timeout):
        return None

    monkeypatch.setattr(aib, "_scan_for_address", fake_scan)

    adapter = AcInfinityBleAdapter()
    with pytest.raises(RuntimeError, match="no AC Infinity BLE advertisement"):
        await adapter.read(make_room(address="AA:BB:CC:DD:EE:FF"))
