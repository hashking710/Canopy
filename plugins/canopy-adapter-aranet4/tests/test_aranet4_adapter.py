import struct

import pytest
from canopy_adapter_aranet4 import Aranet4Adapter, decode_aranet4_reading
from canopy_agent.models import Room


def make_room(**adapter_config) -> Room:
    return Room(
        id="aranet4-room", room_type="greenhouse", path="~/aranet4-room",
        adapter_type="aranet4", metric_config={}, adapter_config=adapter_config,
    )


# ---- decode — pure, self-constructed byte layout (see module docstring's honesty note)


def test_decode_aranet4_reading_round_trips_a_constructed_layout():
    raw = struct.pack("<HHHBB", 800, 440, 10132, 55, 90)  # co2=800ppm, temp raw=440, pressure raw=10132
    reading = decode_aranet4_reading(raw)
    assert reading.co2_ppm == 800.0
    assert reading.temp_c == pytest.approx(22.0)  # 440 / 20.0
    assert reading.pressure_hpa == pytest.approx(1013.2)  # 10132 / 10.0
    assert reading.humidity_pct == 55.0
    assert reading.battery_pct == 90.0


def test_decode_aranet4_reading_too_short_raises():
    with pytest.raises(RuntimeError, match="expected at least 7 bytes"):
        decode_aranet4_reading(bytes(3))


def test_decode_aranet4_reading_ignores_trailing_bytes():
    raw = struct.pack("<HHHBB", 500, 400, 10100, 50, 80) + b"\x01\x02"  # interval/ago fields, not decoded
    reading = decode_aranet4_reading(raw)
    assert reading.co2_ppm == 500.0


# ---- config validation ----------------------------------------------------------------


async def test_read_without_address_raises():
    adapter = Aranet4Adapter()
    with pytest.raises(RuntimeError, match="adapter_config.address"):
        await adapter.read(make_room())


def test_plugin_metadata_is_set():
    assert Aranet4Adapter.plugin_name == "Aranet4 (BLE CO2)"
    assert "address" in Aranet4Adapter.config_schema
    assert set(Aranet4Adapter.default_metric_config) == {"co2_ppm", "temp_f", "rh_pct", "pressure_hpa"}
