"""
Atlas Scientific EZO circuits — pH, EC (conductivity), DO (dissolved oxygen), ORP, and
RTD (temperature) probes, over I2C. Real fertigation/reservoir water-quality
monitoring, not just climate — the same category of "genuinely useful for cultivation
compliance/quality, currently unmonitored" gap PAR light sensors fill on the climate
side. Like canopy-adapter-gpio, this talks to real hardware and can't be verified
end-to-end without a physical EZO circuit — the ASCII command/response protocol below
is implemented from Atlas Scientific's own published datasheets (a real, simple,
well-documented protocol, not reverse-engineered), and what's genuinely unit-tested
is the response-parsing logic, not the I2C transaction itself.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, ClassVar

from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room

if TYPE_CHECKING:
    from smbus2 import SMBus

READ_COMMAND = b"R"
# Atlas Scientific's own datasheets specify 300ms as sufficient processing time for
# a reading on every EZO circuit type except EC, which needs up to 600ms.
READ_DELAY_SECONDS = 0.3
EC_READ_DELAY_SECONDS = 0.6
RESPONSE_BUFFER_SIZE = 32

# EZO response status codes, per Atlas Scientific's I2C protocol documentation.
STATUS_SUCCESS = 1
STATUS_SYNTAX_ERROR = 2
STATUS_STILL_PROCESSING = 254
STATUS_NO_DATA = 255


def _import_smbus2():
    # Same reasoning as canopy-adapter-gpio: smbus2 imports the POSIX-only stdlib
    # `fcntl` module at its own top level, so importing it anywhere at this module's
    # top level would break installing/testing this package anywhere but Linux.
    try:
        from smbus2 import SMBus, i2c_msg
    except ImportError as exc:
        raise RuntimeError(
            "smbus2 is not usable in this environment (it requires Linux's i2c-dev, "
            "e.g. running on a real Raspberry Pi) — EZO probes can't be read here"
        ) from exc
    return SMBus, i2c_msg


class AtlasEzoAdapter(SensorAdapter):
    """
    room.adapter_config shape:
        {
          "sensors": [
            {"metric": "ph", "kind": "ph", "i2c_bus": 1, "i2c_address": "0x63"},
            {"metric": "ec_us_cm", "kind": "ec", "i2c_bus": 1, "i2c_address": "0x64",
             "field_index": 0},
            {"metric": "do_mg_l", "kind": "do", "i2c_bus": 1, "i2c_address": "0x61"},
            {"metric": "res_temp_f", "kind": "rtd", "i2c_bus": 1, "i2c_address": "0x66"}
          ]
        }

    "kind" only affects the processing delay (EC circuits need longer, per Atlas
    Scientific's datasheet) and, for "rtd", the C->F conversion — pH/EC/DO/ORP values
    aren't temperature and are returned as-is. EC circuits report a comma-separated
    line by default (EC, TDS, salinity, specific gravity, in that order, for whichever
    outputs are enabled on the circuit) — "field_index" (default 0) picks which one.
    """

    plugin_name = "Atlas Scientific EZO (I2C)"
    plugin_description = (
        "Atlas Scientific EZO circuits — pH, EC, dissolved oxygen, ORP, and RTD "
        "temperature probes, for fertigation/reservoir water-quality monitoring."
    )
    config_schema: ClassVar[dict[str, str]] = {
        "sensors": "list of {metric, kind ('ph'|'ec'|'do'|'orp'|'rtd'), i2c_bus, "
        "i2c_address, field_index (EC only, default 0)}",
    }

    def __init__(self) -> None:
        self._i2c_buses: dict[int, SMBus] = {}

    async def connect(self, room: Room) -> None:
        pass  # buses opened lazily on first read(), see _get_bus

    async def disconnect(self, room: Room) -> None:
        pass  # buses are cached and shared across rooms; never torn down per-room,
        # same as every other adapter (see adapters/registry.py's get_adapter)

    async def read(self, room: Room) -> dict[str, float]:
        sensors = room.adapter_config.get("sensors")
        if not sensors:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.sensors configured")

        values: dict[str, float] = {}
        for sensor in sensors:
            kind = sensor.get("kind")
            if kind not in ("ph", "ec", "do", "orp", "rtd"):
                raise RuntimeError(f"room '{room.id}': unknown EZO probe kind '{kind}'")
            metric = sensor.get("metric")
            if not metric:
                raise RuntimeError(f"room '{room.id}': an EZO sensor entry is missing 'metric'")

            bus = self._get_bus(sensor.get("i2c_bus", 1))
            address = _parse_i2c_address(sensor["i2c_address"])
            delay = EC_READ_DELAY_SECONDS if kind == "ec" else READ_DELAY_SECONDS
            raw = _read_ezo_raw(bus, address, delay)
            text = parse_ezo_response(raw)

            if kind == "ec":
                field_index = int(sensor.get("field_index", 0))
                value = _extract_ec_field(text, field_index)
            else:
                value = float(text)
                if kind == "rtd":
                    value = value * 9 / 5 + 32

            values[metric] = value
        return values

    def _get_bus(self, bus_number: int) -> SMBus:
        if bus_number not in self._i2c_buses:
            SMBus, _ = _import_smbus2()
            self._i2c_buses[bus_number] = SMBus(bus_number)
        return self._i2c_buses[bus_number]


def _parse_i2c_address(address) -> int:
    if isinstance(address, str):
        return int(address, 0)  # accepts "0x63" or "99"
    return int(address)


def parse_ezo_response(raw: bytes) -> str:
    """Split out from the I2C transaction so response parsing is directly
    unit-testable. raw[0] is the status code; the rest (up to a null terminator) is
    the ASCII result string."""
    if not raw:
        raise RuntimeError("EZO device returned an empty response")
    status = raw[0]
    if status == STATUS_SUCCESS:
        body = raw[1:]
        end = body.index(0) if 0 in body else len(body)
        return body[:end].decode("ascii").strip()
    if status == STATUS_SYNTAX_ERROR:
        raise RuntimeError("EZO device reported a syntax error for the last command")
    if status == STATUS_STILL_PROCESSING:
        raise RuntimeError("EZO device was still processing the reading (read attempted too soon)")
    if status == STATUS_NO_DATA:
        raise RuntimeError("EZO device has no data to send")
    raise RuntimeError(f"EZO device returned an unrecognized status code {status}")


def _extract_ec_field(text: str, field_index: int) -> float:
    fields = text.split(",")
    if field_index >= len(fields):
        raise RuntimeError(f"EZO EC response '{text}' has no field at index {field_index}")
    try:
        return float(fields[field_index])
    except ValueError as exc:
        raise RuntimeError(f"EZO EC response field '{fields[field_index]}' is not numeric") from exc


def _read_ezo_raw(bus: SMBus, address: int, delay_seconds: float) -> bytes:
    # EZO circuits have no register model — they just want the raw ASCII command
    # written directly (same "no register, just raw bytes" shape as SHT31's command
    # protocol), hence i2c_msg's raw block write/read rather than a register-addressed
    # SMBus block transaction.
    _, i2c_msg = _import_smbus2()
    bus.i2c_rdwr(i2c_msg.write(address, READ_COMMAND))
    time.sleep(delay_seconds)
    read = i2c_msg.read(address, RESPONSE_BUFFER_SIZE)
    bus.i2c_rdwr(read)
    return bytes(read)
