"""
Aranet4 — a real NDIR (non-dispersive infrared) CO2 sensor, genuinely accurate
(unlike cheap eCO2/VOC-estimate sensors) and the one the cultivation/grow community
actually reaches for when CO2 supplementation is in play. BLE-only, no app account,
no cloud dependency.

Confidence note: Aranet doesn't publish an official BLE protocol spec, but the
community `aranet4` PyPI package (actively maintained, widely used) has reverse-
engineered and documented the "current readings" characteristic's exact byte layout.
This adapter is implemented from recollection of that documented layout, not copied
from the library's source directly — meaning there's real risk the exact byte
offsets below don't perfectly match a real device. The decode function is pure and
tested for internal consistency (a self-constructed byte layout decodes back to the
values that constructed it), which proves this adapter's own parsing logic is
self-consistent — it does not prove the byte offsets match a real Aranet4's actual
output. Cross-check against the `aranet4` library or a real device's readings before
trusting production values.
"""

from __future__ import annotations

import struct
from typing import ClassVar

from bleak import BleakClient
from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room

CONNECT_TIMEOUT_SECONDS = 10.0

# Aranet's custom BLE service/characteristic — community-documented via the `aranet4`
# project, not an official published spec.
CURRENT_READINGS_CHARACTERISTIC = "f0cd3001-95da-4f4b-9ac8-aa55d312af0c"


class Aranet4Adapter(SensorAdapter):
    """
    room.adapter_config shape:
        {"address": "AA:BB:CC:DD:EE:FF"}   # the Aranet4's BLE MAC address

    Reports co2_ppm, temp_f, rh_pct, and pressure_hpa in one BLE characteristic read
    — Aranet4 packs all four (plus battery/status/interval, not surfaced here) into
    one "current readings" response.
    """

    plugin_name = "Aranet4 (BLE CO2)"
    plugin_description = "Aranet4 NDIR CO2 sensor — accurate real CO2, plus temp/RH/pressure, over BLE."
    config_schema: ClassVar[dict[str, str]] = {"address": "Aranet4's BLE MAC address"}

    async def connect(self, room: Room) -> None:
        pass  # connects fresh on every read(), see read()

    async def disconnect(self, room: Room) -> None:
        pass  # no persistent connection is held between reads

    async def read(self, room: Room) -> dict[str, float]:
        address = room.adapter_config.get("address")
        if not address:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.address")

        async with BleakClient(address, timeout=CONNECT_TIMEOUT_SECONDS) as client:
            raw = await client.read_gatt_char(CURRENT_READINGS_CHARACTERISTIC)

        reading = decode_aranet4_reading(bytes(raw))
        return {
            "co2_ppm": reading.co2_ppm,
            "temp_f": reading.temp_c * 9 / 5 + 32,
            "rh_pct": reading.humidity_pct,
            "pressure_hpa": reading.pressure_hpa,
        }


class Aranet4Reading:
    __slots__ = ("co2_ppm", "temp_c", "pressure_hpa", "humidity_pct", "battery_pct")

    def __init__(self, co2_ppm: float, temp_c: float, pressure_hpa: float, humidity_pct: float, battery_pct: float) -> None:
        self.co2_ppm = co2_ppm
        self.temp_c = temp_c
        self.pressure_hpa = pressure_hpa
        self.humidity_pct = humidity_pct
        self.battery_pct = battery_pct


def decode_aranet4_reading(raw: bytes) -> Aranet4Reading:
    """raw is the "current readings" characteristic's value: co2 (uint16, ppm direct),
    temperature (uint16, raw/20.0 = C), pressure (uint16, raw/10.0 = hPa), humidity
    (uint8, % direct), battery (uint8, %) — all little-endian, at least 7 bytes."""
    if len(raw) < 7:
        raise RuntimeError(f"aranet4: expected at least 7 bytes, got {len(raw)}")
    co2_ppm, raw_temp, raw_pressure, humidity_pct, battery_pct = struct.unpack_from("<HHHBB", raw, 0)
    return Aranet4Reading(
        co2_ppm=float(co2_ppm),
        temp_c=raw_temp / 20.0,
        pressure_hpa=raw_pressure / 10.0,
        humidity_pct=float(humidity_pct),
        battery_pct=float(battery_pct),
    )
