import asyncio
import struct
from typing import Any, ClassVar

from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room
from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient

REGISTER_READERS = {"holding": "read_holding_registers", "input": "read_input_registers"}
DATA_TYPE_SIZES = {"int16": 1, "uint16": 1, "int32": 2, "uint32": 2, "float32": 2}


class ModbusAdapter(SensorAdapter):
    """
    Generic Modbus TCP/RTU adapter — unlike AC Infinity's plugin, Modbus itself carries
    no self-describing metadata (a register is just a number; what it means is entirely
    device-specific, published in each vendor's own "Modbus register map" document).
    So this adapter can't ship a fixed set of known metrics — instead, each room's
    adapter_config describes its own device's register map. This mirrors how Home
    Assistant's own generic `modbus` integration works, for the same reason.

    Because Modbus is an open standard (not a vendor secret needing reverse-engineering,
    unlike AC Infinity's cloud API), this adapter can talk to any Modbus-capable device
    out of the box — commercial environmental controllers (Argus, Priva, Growlink) and
    industrial I/O gateways commonly expose a Modbus interface even when their own cloud
    API is enterprise-gated or undocumented. See docs/architecture.md for the sensor
    hardware research this plugin priority came out of.

    `room.adapter_config` shape:
        {
          "transport": "tcp" | "rtu",             # default "tcp"
          # tcp:
          "host": "192.168.1.50", "port": 502,     # port default 502
          # rtu:
          "serial_port": "/dev/ttyUSB0", "baudrate": 9600,  # baudrate default 9600
          "device_id": 1,                          # Modbus device/unit address, default 1
          "registers": [
            {
              "metric": "temp_f",                  # -> Reading.metric / room.metric_config key
              "address": 30001,
              "register_type": "holding" | "input", # default "holding"
              "data_type": "int16" | "uint16" | "int32" | "uint32" | "float32",  # default "int16"
              "word_order": "big" | "little",       # only for 32-bit types; default "big".
                                                     # Real devices disagree on this — check the
                                                     # vendor's register map, don't assume.
              "scale": 1.0,                         # value = raw * scale + offset
              "offset": 0.0,
            },
            ...
          ],
        }
    """

    plugin_name = "Modbus (TCP/RTU)"
    plugin_description = (
        "Generic adapter for any Modbus TCP or RTU device — describe the device's own "
        "register map in adapter_config; this doesn't assume any particular vendor."
    )
    category: ClassVar[str] = "local"
    config_schema: ClassVar[dict[str, str]] = {
        "transport": '"tcp" or "rtu", default "tcp"',
        "host": "TCP only: device IP/hostname",
        "port": "TCP only: Modbus TCP port, default 502",
        "serial_port": "RTU only: e.g. /dev/ttyUSB0 or COM3",
        "baudrate": "RTU only: default 9600",
        "device_id": "Modbus device/unit address, default 1",
        "registers": "list of {metric, address, register_type, data_type, word_order, scale, offset}",
    }

    def __init__(self) -> None:
        self._clients: dict[tuple, Any] = {}
        self._locks: dict[tuple, asyncio.Lock] = {}

    async def connect(self, room: Room) -> None:
        pass  # lazy: the target connection is established on first read(), see _get_client

    async def disconnect(self, room: Room) -> None:
        pass  # connections are cached per target and shared across every room using it;
        # never called by the poller today anyway (see adapters/registry.py's get_adapter)

    async def read(self, room: Room) -> dict[str, float]:
        config = room.adapter_config
        registers = config.get("registers")
        if not registers:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.registers configured")

        client = await self._get_client(room.id, config)
        device_id = config.get("device_id", 1)

        values: dict[str, float] = {}
        for reg in registers:
            values[reg["metric"]] = await self._read_one(client, device_id, reg)
        return values

    def _target_key(self, config: dict) -> tuple:
        transport = config.get("transport", "tcp")
        if transport == "rtu":
            if "serial_port" not in config:
                raise RuntimeError("adapter_config.transport is 'rtu' but 'serial_port' is missing")
            return ("rtu", config["serial_port"], config.get("baudrate", 9600))
        if transport == "tcp":
            if "host" not in config:
                raise RuntimeError("adapter_config.transport is 'tcp' but 'host' is missing")
            return ("tcp", config["host"], config.get("port", 502))
        raise RuntimeError(f"unknown adapter_config.transport '{transport}' (must be 'tcp' or 'rtu')")

    async def _get_client(self, room_id: str, config: dict):
        key = self._target_key(config)
        if key not in self._clients:
            if key[0] == "rtu":
                _, serial_port, baudrate = key
                self._clients[key] = AsyncModbusSerialClient(serial_port, baudrate=baudrate)
            else:
                _, host, port = key
                self._clients[key] = AsyncModbusTcpClient(host, port=port)
            self._locks[key] = asyncio.Lock()

        client = self._clients[key]
        if not client.connected:
            # Two rooms sharing one device could otherwise both see `not connected` and
            # race to call connect() simultaneously; the lock makes the second one just
            # wait and reuse the first's connection instead of opening a duplicate.
            async with self._locks[key]:
                if not client.connected:
                    if not await client.connect():
                        raise RuntimeError(f"could not connect to Modbus device at {key[1:]} for room '{room_id}'")
        return client

    async def _read_one(self, client, device_id: int, reg: dict) -> float:
        metric = reg["metric"]
        address = reg["address"]
        register_type = reg.get("register_type", "holding")
        data_type = reg.get("data_type", "int16")
        word_order = reg.get("word_order", "big")
        scale = reg.get("scale", 1.0)
        offset = reg.get("offset", 0.0)

        reader_name = REGISTER_READERS.get(register_type)
        if reader_name is None:
            raise RuntimeError(f"metric '{metric}': unknown register_type '{register_type}' (must be 'holding' or 'input')")
        count = DATA_TYPE_SIZES.get(data_type)
        if count is None:
            raise RuntimeError(f"metric '{metric}': unsupported data_type '{data_type}'")

        response = await getattr(client, reader_name)(address, count=count, device_id=device_id)
        if response.isError():
            raise RuntimeError(f"metric '{metric}': Modbus error reading {register_type} register {address}: {response}")

        raw = _decode_registers(response.registers, data_type, word_order)
        return raw * scale + offset


def _decode_registers(registers: list[int], data_type: str, word_order: str) -> float:
    if data_type in ("int16", "uint16"):
        raw = registers[0]
        if data_type == "int16" and raw >= 0x8000:
            raw -= 0x10000
        return float(raw)

    # 32-bit types span two consecutive 16-bit registers. Real devices genuinely
    # disagree on which one is the high word — this is one of the most common sources
    # of wrong readings in Modbus integrations, not a hypothetical edge case, hence
    # word_order being configurable rather than assumed.
    hi, lo = registers if word_order == "big" else (registers[1], registers[0])
    packed = struct.pack(">HH", hi, lo)
    if data_type == "uint32":
        return float(struct.unpack(">I", packed)[0])
    if data_type == "int32":
        return float(struct.unpack(">i", packed)[0])
    if data_type == "float32":
        return float(struct.unpack(">f", packed)[0])
    raise RuntimeError(f"unsupported data_type '{data_type}'")  # pragma: no cover — guarded by DATA_TYPE_SIZES lookup earlier
