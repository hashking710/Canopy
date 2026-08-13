"""
AC Infinity — Bluetooth-only UIS controllers (Controller 67, base 69/"69 Pro", and
similar) that never sync to AC Infinity's cloud, so canopy-adapter-ac-infinity's
cloud/WiFi adapter can't reach them at all.

Confidence note, different in kind from most "implemented from memory" caveats
elsewhere in this ecosystem: the byte layout below is a direct, byte-for-byte port
of a real, existing MIT-licensed library's actual source code —
github.com/hunterjm/ac-infinity-ble (published to PyPI as `ac-infinity-ble`),
specifically its `protocol.py:parse_manufacturer_data` and `util.py`'s bit-math
helpers — fetched and read directly, not reconstructed from a forum thread summary
or from memory. The temperature-is-Celsius and VPD-is-kPa interpretations are
further corroborated against that same author's separate, real Home Assistant
integration (github.com/hunterjm/ac-infinity-hacs), whose `sensor.py` declares
`UnitOfTemperature.CELSIUS` for the raw value this adapter also reads, with no
conversion applied — i.e. two independent, real pieces of software agree on what
the raw bytes mean. That upstream library's own README describes itself as
"Pre-Alpha", so real hardware verification is still warranted before trusting
production values, but this is a meaningfully stronger starting point than a
from-memory implementation.

Passive only, by design: every value comes from the BLE advertisement's
manufacturer-specific data (company ID 2306 / 0x0902) — the same "no active
connection" advertising path canopy-adapter-ble's BleAdvertisementAdapter already
uses. This adapter never connects to or writes anything to the controller, so there
is no risk of it accidentally changing a fan's speed or mode. Setting fan speed is
deliberately out of scope entirely: Canopy's SensorAdapter interface is read-only by
design (see adapters/base.py — there is no write()/set() method anywhere in it), and
a wrong write to real grow-room fan hardware is a categorically worse mistake than a
wrong read.
"""

from __future__ import annotations

import asyncio
import struct
from typing import ClassVar

from bleak import BleakScanner
from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room

SCAN_TIMEOUT_SECONDS = 15.0

# AC Infinity's registered BLE manufacturer ID, from ac-infinity-ble's const.py
# (MANUFACTURER_ID = 2306). Advertisement manufacturer_data is keyed by this in
# bleak's AdvertisementData.
MANUFACTURER_ID = 2306

# Controller types that also report VPD (ac-infinity-ble's protocol.py:
# `if device.version >= 3 and device.type in [7, 9, 11, 12]`).
_VPD_CAPABLE_TYPES = (7, 9, 11, 12)


class AcInfinityBleAdapter(SensorAdapter):
    """
    room.adapter_config shape:
        {"address": "AA:BB:CC:DD:EE:FF"}   # the controller's BLE MAC address

    Reports temp_f, rh_pct, and fan_pct (0-100, linearly mapped from the
    controller's own 0-10 speed-level scale — the same range the upstream Home
    Assistant integration's fan.py uses, `SPEED_RANGE = (1, 10)`) always, plus
    vpd_kpa only on controller types/firmware that report it (see
    _VPD_CAPABLE_TYPES) — silently omitted otherwise, same "report what's actually
    there" approach as canopy-adapter-shelly's two API generations.
    """

    plugin_name = "AC Infinity (Bluetooth-only controllers)"
    plugin_description = (
        "For AC Infinity's Bluetooth-only UIS controllers (Controller 67, 69 Pro, "
        "and similar) that never sync to the cloud — a passive BLE advertisement "
        "read, no app account and no active connection to the controller."
    )
    category: ClassVar[str] = "bluetooth"
    config_schema: ClassVar[dict[str, str]] = {
        "address": "BLE MAC address of the controller",
    }
    default_metric_config: ClassVar[dict[str, dict]] = {
        "temp_f": {"label": "temp", "unit": "°F", "decimals": 1},
        "rh_pct": {"label": "RH", "unit": "%", "decimals": 1},
        "fan_pct": {"label": "fan speed", "unit": "%", "decimals": 0},
    }
    supports_discovery: ClassVar[bool] = True

    async def connect(self, room: Room) -> None:
        pass  # passive advertisement read only, see read()

    async def disconnect(self, room: Room) -> None:
        pass  # no connection is ever held open

    @classmethod
    async def discover(cls) -> list[dict]:
        found = await _scan_for_ac_infinity_advertisements(SCAN_TIMEOUT_SECONDS)
        return _format_discovery_results(found)

    async def read(self, room: Room) -> dict[str, float]:
        address = room.adapter_config.get("address")
        if not address:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.address")

        payload = await _scan_for_address(address, SCAN_TIMEOUT_SECONDS)
        if payload is None:
            raise RuntimeError(
                f"room '{room.id}': no AC Infinity BLE advertisement received from "
                f"{address} within {SCAN_TIMEOUT_SECONDS}s"
            )
        return _reading_from_manufacturer_data(payload)


def _get_short(data: bytes, offset: int) -> int:
    """Big-endian signed 16-bit — matches ac-infinity-ble's util.py:get_short
    (ctypes.c_int16 of (data[offset] << 8) | data[offset + 1])."""
    return struct.unpack_from(">h", data, offset)[0]


def _get_bits(byte: int, start: int, length: int) -> int:
    """Direct port of ac-infinity-ble's util.py:get_bits — extracts `length` bits
    starting at bit position `start` (0 = most significant)."""
    return (byte >> ((8 - start) - length)) & (255 >> (8 - length))


def parse_ac_infinity_manufacturer_data(data: bytes) -> dict:
    """Direct, byte-for-byte port of ac-infinity-ble's protocol.py:
    parse_manufacturer_data. `data` is the raw manufacturer-specific data bytes for
    company ID MANUFACTURER_ID from a BLE advertisement. Split out from the BLE scan
    so this is directly unit-testable against a constructed byte layout without a
    real device."""
    if len(data) < 19:
        raise RuntimeError(f"ac_infinity_ble: manufacturer data is {len(data)} bytes, need at least 19")

    controller_type = data[12]
    version = data[11]
    flags = data[13]
    result: dict = {
        "type": controller_type,
        "version": version,
        "fan_state": _get_bits(flags, 2, 2),
        "tmp_state": _get_bits(flags, 4, 2),
        "hum_state": _get_bits(flags, 6, 2),
        "temp_c": _get_short(data, 14) / 100,
        "hum_pct": _get_short(data, 16) / 100,
        "fan_level": data[18],
    }
    if version >= 3 and controller_type in _VPD_CAPABLE_TYPES and len(data) >= 23:
        result["choose_port"] = data[19]
        result["vpd_state"] = _get_bits(data[20], 0, 2)
        result["vpd_kpa"] = _get_short(data, 21) / 100
    return result


def _reading_from_manufacturer_data(data: bytes) -> dict[str, float]:
    parsed = parse_ac_infinity_manufacturer_data(data)
    reading = {
        "temp_f": parsed["temp_c"] * 9 / 5 + 32,
        "rh_pct": parsed["hum_pct"],
        "fan_pct": min(parsed["fan_level"], 10) * 10.0,
    }
    if "vpd_kpa" in parsed:
        reading["vpd_kpa"] = parsed["vpd_kpa"]
    return reading


async def _scan_for_address(address: str, timeout: float) -> bytes | None:
    """Same passive-scan-until-seen shape as canopy-adapter-ble's
    BleAdvertisementAdapter._scan_for_payload."""
    found: dict[str, bytes] = {}

    def on_advertisement(device, advertisement_data) -> None:
        if device.address.upper() != address.upper():
            return
        data = (advertisement_data.manufacturer_data or {}).get(MANUFACTURER_ID)
        if data is not None:
            found["payload"] = bytes(data)

    async with BleakScanner(detection_callback=on_advertisement):
        deadline = asyncio.get_event_loop().time() + timeout
        while "payload" not in found and asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(0.5)

    return found.get("payload")


async def _scan_for_ac_infinity_advertisements(timeout: float) -> dict[str, bytes]:
    """The live-network half of discover() — kept separate from the pure formatting
    step below so tests can monkeypatch this one function directly, same split as
    canopy-adapter-ble/canopy-adapter-shelly use for their own discover()."""
    found: dict[str, bytes] = {}

    def on_advertisement(device, advertisement_data) -> None:
        data = (advertisement_data.manufacturer_data or {}).get(MANUFACTURER_ID)
        if data is not None:
            found[device.address] = bytes(data)

    async with BleakScanner(detection_callback=on_advertisement):
        await asyncio.sleep(timeout)
    return found


def _format_discovery_results(raw: dict[str, bytes]) -> list[dict]:
    """Pure — fully unit-testable without any real BLE traffic. Skips any payload
    that fails to parse (too short / malformed) rather than surfacing a discovery
    error for one bad advertisement out of possibly several found."""
    results = []
    for address, payload in sorted(raw.items()):
        try:
            parsed = parse_ac_infinity_manufacturer_data(payload)
        except RuntimeError:
            continue
        results.append({"address": address, "name": f"AC Infinity controller (type {parsed['type']})"})
    return results
