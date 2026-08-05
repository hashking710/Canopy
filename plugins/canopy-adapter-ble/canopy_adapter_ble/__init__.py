"""
Generic BLE (Bluetooth Low Energy) adapters — the BLE-world counterpart to canopy-
adapter-mqtt's "one adapter, huge ecosystem reach" role. Two connection models, two
adapter classes, since BLE genuinely has two different ways a sensor exposes data:

- **`ble`** (BleAdapter) — connects and reads a GATT characteristic. For devices that
  need an active connection (most BLE peripherals with a battery big enough to not
  mind maintaining one).
- **`ble_advertisement`** (BleAdvertisementAdapter) — passively scans for
  advertisement/broadcast packets, no connection at all. For coin-cell devices that
  save power by broadcasting instead of accepting connections — this is how the
  popular re-flashed Xiaomi Mijia temp/RH sensors (custom ATC/pvvx firmware) work,
  along with a good chunk of the broader BTHome-style sensor ecosystem. Rather than
  guessing at one specific firmware variant's exact byte layout (there are genuinely
  two competing custom-firmware formats with different byte orders in circulation),
  this adapter takes the byte offsets/format as config — same reasoning as Modbus's
  device-described register map, applied to BLE advertisement payloads.

Uses `bleak` (real, cross-platform, actively maintained — the standard choice for
Python BLE today). `ble` connects fresh on every read() rather than holding a
persistent connection: BLE connections are inherently more fragile than a TCP/MQTT
session (range, interference, one peripheral generally serving one central at a
time), and a poll-cycle-driven connect/read/disconnect is a more robust fit than
trying to maintain a long-lived link across 5s poll cycles.

Confidence note, matching canopy-adapter-gpio's honesty pattern: the byte-format
decoding (uint/sint at various widths, float32, all little-endian per BLE's own
convention) is pure, real, and fully unit-tested. The actual BLE connect/read or
scan/receive transaction cannot be verified without a real peripheral nearby — this
is the same category of gap as the AC Infinity Bluetooth adapter that was never
built for exactly this reason.
"""

from __future__ import annotations

import asyncio
import struct
from typing import ClassVar

from bleak import BleakClient, BleakScanner
from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room

CONNECT_TIMEOUT_SECONDS = 10.0
SCAN_TIMEOUT_SECONDS = 15.0

_STRUCT_FORMATS = {
    "uint8": "<B",
    "sint8": "<b",
    "uint16_le": "<H",
    "sint16_le": "<h",
    "uint32_le": "<I",
    "sint32_le": "<i",
    "float32_le": "<f",
}


class BleAdapter(SensorAdapter):
    """
    room.adapter_config shape:
        {
          "address": "AA:BB:CC:DD:EE:FF",
          "characteristics": [
            {"metric": "temp_f", "uuid": "00002a6e-0000-1000-8000-00805f9b34fb",
             "format": "sint16_le", "scale": 0.01, "offset": 0, "c_to_f": true}
          ]
        }

    "format" is one of uint8/sint8/uint16_le/sint16_le/uint32_le/sint32_le/float32_le
    — covers the byte encodings the large majority of simple BLE sensor
    characteristics actually use (including the Bluetooth SIG's own standard
    Environmental Sensing Service characteristics, e.g. 0x2A6E Temperature is a
    sint16 in units of 0.01°C — hence "scale": 0.01 being the natural default for
    that specific characteristic). "c_to_f", if true, converts the scaled value from
    Celsius to Fahrenheit after scale/offset are applied.
    """

    plugin_name = "BLE (generic GATT characteristic)"
    plugin_description = (
        "Reads a numeric value from any BLE device's GATT characteristic — works "
        "with any sensor exposing a plain numeric characteristic, including the "
        "Bluetooth SIG's standard Environmental Sensing Service."
    )
    category: ClassVar[str] = "bluetooth"
    config_schema: ClassVar[dict[str, str]] = {
        "address": "BLE MAC address (or UUID on macOS) of the device",
        "characteristics": "list of {metric, uuid, format, scale, offset, c_to_f}",
    }
    supports_discovery: ClassVar[bool] = True

    async def connect(self, room: Room) -> None:
        pass  # connects fresh on every read(), see read()

    async def disconnect(self, room: Room) -> None:
        pass  # no persistent connection is held between reads

    @classmethod
    async def discover(cls) -> list[dict]:
        return await scan_for_nearby_devices()

    async def read(self, room: Room) -> dict[str, float]:
        config = room.adapter_config
        address = config.get("address")
        if not address:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.address")
        characteristics = config.get("characteristics")
        if not characteristics:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.characteristics configured")

        values: dict[str, float] = {}
        async with BleakClient(address, timeout=CONNECT_TIMEOUT_SECONDS) as client:
            for char in characteristics:
                metric = char.get("metric")
                uuid = char.get("uuid")
                if not metric or not uuid:
                    raise RuntimeError(f"room '{room.id}': a characteristic entry is missing 'metric' or 'uuid'")
                raw = await client.read_gatt_char(uuid)
                values[metric] = decode_ble_value(bytes(raw), char)
        return values


def decode_ble_value(raw: bytes, char: dict) -> float:
    """Split out from the BLE transaction so byte-format decoding is directly
    unit-testable without a real device."""
    fmt = char.get("format", "float32_le")
    struct_fmt = _STRUCT_FORMATS.get(fmt)
    if struct_fmt is None:
        raise RuntimeError(f"ble: unknown format '{fmt}' (must be one of {sorted(_STRUCT_FORMATS)})")

    expected_size = struct.calcsize(struct_fmt)
    if len(raw) < expected_size:
        raise RuntimeError(f"ble: characteristic value is {len(raw)} bytes, need at least {expected_size} for '{fmt}'")

    (raw_value,) = struct.unpack(struct_fmt, raw[:expected_size])
    scale = char.get("scale", 1.0)
    offset = char.get("offset", 0.0)
    value = raw_value * scale + offset
    if char.get("c_to_f"):
        value = value * 9 / 5 + 32
    return value


async def scan_for_nearby_devices() -> list[dict]:
    """Shared by both BLE adapter classes — a passive scan sees the same
    advertisements regardless of whether a given device will end up being talked to
    via GATT connection (BleAdapter) or advertisement parsing
    (BleAdvertisementAdapter), so there's no reason to scan twice or differently."""
    found = await BleakScanner.discover(timeout=SCAN_TIMEOUT_SECONDS, return_adv=True)
    return [
        {"address": device.address, "name": device.name or adv.local_name, "rssi": adv.rssi}
        for device, adv in found.values()
    ]


class BleAdvertisementAdapter(SensorAdapter):
    """
    room.adapter_config shape:
        {
          "address": "AA:BB:CC:DD:EE:FF",
          "service_data_uuid": "0000181a-0000-1000-8000-00805f9b34fb",
          "fields": [
            {"metric": "temp_f", "byte_offset": 6, "format": "sint16_le",
             "scale": 0.01, "c_to_f": true},
            {"metric": "rh_pct", "byte_offset": 8, "format": "uint8"}
          ]
        }

    "service_data_uuid" selects which advertisement service-data payload to read
    fields from (a device can advertise several at once) — find it for your specific
    device with any BLE scanner app/tool. "byte_offset" is the offset within that
    payload's own data (not the whole advertisement packet), letting one config
    describe any advertisement-based sensor's layout — including either of the
    competing Xiaomi Mijia custom-firmware byte layouts in circulation, by setting
    offsets/formats to match whichever one a given device actually uses, rather than
    this adapter guessing at one.
    """

    plugin_name = "BLE (passive advertisement scan)"
    plugin_description = (
        "Passively scans for BLE advertisement/broadcast packets — for coin-cell "
        "sensors that broadcast instead of accepting connections (e.g. re-flashed "
        "Xiaomi Mijia temp/RH sensors, BTHome-style devices)."
    )
    category: ClassVar[str] = "bluetooth"
    config_schema: ClassVar[dict[str, str]] = {
        "address": "BLE MAC address of the device",
        "service_data_uuid": "Which advertisement service-data UUID to read from",
        "fields": "list of {metric, byte_offset, format, scale, offset, c_to_f}",
    }
    supports_discovery: ClassVar[bool] = True

    async def connect(self, room: Room) -> None:
        pass

    async def disconnect(self, room: Room) -> None:
        pass

    @classmethod
    async def discover(cls) -> list[dict]:
        return await scan_for_nearby_devices()

    async def read(self, room: Room) -> dict[str, float]:
        config = room.adapter_config
        address = config.get("address")
        if not address:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.address")
        service_data_uuid = config.get("service_data_uuid")
        if not service_data_uuid:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.service_data_uuid")
        fields = config.get("fields")
        if not fields:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.fields configured")

        payload = await self._scan_for_payload(address, service_data_uuid)

        values: dict[str, float] = {}
        for field in fields:
            metric = field.get("metric")
            byte_offset = field.get("byte_offset")
            if metric is None or byte_offset is None:
                raise RuntimeError(f"room '{room.id}': a field entry is missing 'metric' or 'byte_offset'")
            values[metric] = decode_ble_value(payload[byte_offset:], field)
        return values

    async def _scan_for_payload(self, address: str, service_data_uuid: str) -> bytes:
        found: dict[str, bytes] = {}

        def on_advertisement(device, advertisement_data) -> None:
            if device.address.upper() != address.upper():
                return
            data = (advertisement_data.service_data or {}).get(service_data_uuid)
            if data is not None:
                found["payload"] = bytes(data)

        async with BleakScanner(detection_callback=on_advertisement):
            deadline = asyncio.get_event_loop().time() + SCAN_TIMEOUT_SECONDS
            while "payload" not in found and asyncio.get_event_loop().time() < deadline:
                await asyncio.sleep(0.5)

        if "payload" not in found:
            raise RuntimeError(
                f"no advertisement with service data '{service_data_uuid}' received "
                f"from {address} within {SCAN_TIMEOUT_SECONDS}s"
            )
        return found["payload"]
