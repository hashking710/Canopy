"""
Tuya local protocol — the huge ecosystem of cheap sensors sold under the generic
"Smart Life" / "Tuya Smart" app branding (soil moisture, temp/RH, and more, often
white-labeled under dozens of storefront names for the same underlying hardware).

Built on the real `tinytuya` package (mature, actively maintained, the standard
Python choice for this) rather than hand-rolling Tuya's custom binary framing and
AES encryption from memory — unlike this project's other protocols (Modbus, BLE,
I2C), getting a custom crypto/framing protocol subtly wrong doesn't just risk a wrong
reading, it risks silently-garbled data that still looks like a plausible number.
Reusing a real, trusted, widely-used implementation is the responsible choice here,
the same reasoning that justifies using `pymodbus`/`bleak`/`smbus2` for their own
protocols instead of reimplementing them too.

Real setup friction, documented honestly rather than glossed over: getting a
device's `local_key` requires a (free) Tuya IoT Cloud developer account and linking
the device once — see tinytuya's own `tinytuya wizard` setup tool. Actual runtime
communication afterward is purely local (no cloud round-trip per reading), which is
the point of using the local protocol at all rather than Tuya's cloud API.
"""

from __future__ import annotations

import asyncio
from typing import ClassVar

import tinytuya
from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room


class TuyaAdapter(SensorAdapter):
    """
    room.adapter_config shape:
        {
          "device_id": "...",
          "local_key": "...",
          "ip": "192.168.1.50",
          "version": 3.3,
          "dps": {"soil_pct": "5", "temp_f": "19"}
        }

    "dps" maps metric keys to Tuya "data point" numbers (as strings, matching
    tinytuya's own status() response shape) — entirely device-specific, same "device
    describes its own shape" approach as Modbus's register map, since DP numbering
    isn't standardized across Tuya device types. "version" is the device's Tuya
    protocol version (3.1/3.3/3.4 are the common ones) — get it via `tinytuya
    wizard`'s device scan, guessing wrong causes a connection/decrypt failure, not a
    silently wrong reading, so this is safe to get wrong and retry.
    """

    plugin_name = "Tuya (local protocol)"
    plugin_description = (
        "Tuya/Smart Life-branded devices over the local protocol (via tinytuya) — "
        "no cloud round-trip at runtime, though getting a device's local_key needs "
        "a one-time Tuya IoT Cloud developer setup step."
    )
    config_schema: ClassVar[dict[str, str]] = {
        "device_id": "Tuya device id",
        "local_key": "Tuya local key (from the Tuya IoT Cloud developer portal)",
        "ip": "Device IP on your LAN",
        "version": "Tuya protocol version (3.1, 3.3, or 3.4) — see tinytuya wizard",
        "dps": "{metric_key: dp_number_as_string} — device-specific, see tinytuya wizard",
    }

    async def connect(self, room: Room) -> None:
        pass  # tinytuya connects synchronously per status() call; see read()

    async def disconnect(self, room: Room) -> None:
        pass  # no persistent connection held between reads

    async def read(self, room: Room) -> dict[str, float]:
        config = room.adapter_config
        device_id = config.get("device_id")
        local_key = config.get("local_key")
        ip = config.get("ip")
        if not device_id or not local_key or not ip:
            raise RuntimeError(f"room '{room.id}' needs adapter_config.device_id, local_key, and ip")
        dps_map = config.get("dps")
        if not dps_map:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.dps configured")
        version = float(config.get("version", 3.3))

        # tinytuya's Device.status() is a real blocking socket call — offloaded to a
        # thread so it doesn't stall the event loop the way every other adapter's
        # async I/O already doesn't.
        status = await asyncio.to_thread(_fetch_status, device_id, ip, local_key, version)
        return extract_tuya_metrics(status, dps_map)


def _fetch_status(device_id: str, ip: str, local_key: str, version: float) -> dict:
    device = tinytuya.Device(device_id, address=ip, local_key=local_key, version=version)
    status = device.status()
    if not isinstance(status, dict) or "dps" not in status:
        raise RuntimeError(f"tuya: unexpected status() response from device '{device_id}': {status!r}")
    return status


def extract_tuya_metrics(status: dict, dps_map: dict[str, str]) -> dict[str, float]:
    """Split out from the network call so DP extraction is directly unit-testable
    against a real tinytuya-shaped response without a device."""
    dps = status.get("dps", {})
    values: dict[str, float] = {}
    for metric, dp_number in dps_map.items():
        if dp_number not in dps:
            raise RuntimeError(f"tuya: no data point '{dp_number}' in device response (has: {sorted(dps)})")
        raw_value = dps[dp_number]
        try:
            values[metric] = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"tuya: data point '{dp_number}' value {raw_value!r} is not numeric") from exc
    return values
