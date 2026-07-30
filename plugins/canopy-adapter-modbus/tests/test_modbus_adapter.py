import struct

import pytest
from canopy_adapter_modbus import ModbusAdapter, _decode_registers
from canopy_agent.models import Room
from pymodbus.datastore import ModbusDeviceContext, ModbusSequentialDataBlock, ModbusServerContext
from pymodbus.server import ModbusTcpServer

TEST_PORT = 15502


def make_room(**adapter_config) -> Room:
    return Room(
        id="modbus-room", room_type="greenhouse", path="~/modbus-room",
        adapter_type="modbus", metric_config={}, adapter_config=adapter_config,
    )


# ---- pure decode logic — no network involved -------------------------------------


def test_decode_int16_positive():
    assert _decode_registers([850], "int16", "big") == 850.0


def test_decode_int16_twos_complement_negative():
    # 65486 as an unsigned 16-bit word is -50 as signed two's complement
    assert _decode_registers([65486], "int16", "big") == -50.0


def test_decode_uint16_stays_unsigned():
    assert _decode_registers([65486], "uint16", "big") == 65486.0


def test_decode_float32_big_word_order():
    hi, lo = struct.unpack(">HH", struct.pack(">f", 12.34))
    assert _decode_registers([hi, lo], "float32", "big") == pytest.approx(12.34, abs=1e-3)


def test_decode_float32_little_word_order():
    hi, lo = struct.unpack(">HH", struct.pack(">f", 12.34))
    # little word order means the low word arrives first over the wire
    assert _decode_registers([lo, hi], "float32", "little") == pytest.approx(12.34, abs=1e-3)


def test_decode_int32_negative():
    hi, lo = struct.unpack(">HH", struct.pack(">i", -1000))
    assert _decode_registers([hi, lo], "int32", "big") == -1000.0


def test_decode_uint32():
    hi, lo = struct.unpack(">HH", struct.pack(">I", 70000))
    assert _decode_registers([hi, lo], "uint32", "big") == 70000.0


# ---- config validation — no network involved --------------------------------------


async def test_read_without_registers_raises():
    adapter = ModbusAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.registers"):
        await adapter.read(make_room())


async def test_unknown_transport_raises():
    adapter = ModbusAdapter()
    with pytest.raises(RuntimeError, match="unknown adapter_config.transport"):
        await adapter.read(make_room(transport="carrier-pigeon", registers=[{"metric": "x", "address": 0}]))


async def test_tcp_without_host_raises():
    adapter = ModbusAdapter()
    with pytest.raises(RuntimeError, match="'host' is missing"):
        await adapter.read(make_room(transport="tcp", registers=[{"metric": "x", "address": 0}]))


async def test_rtu_without_serial_port_raises():
    adapter = ModbusAdapter()
    with pytest.raises(RuntimeError, match="'serial_port' is missing"):
        await adapter.read(make_room(transport="rtu", registers=[{"metric": "x", "address": 0}]))


def test_plugin_metadata_is_set():
    assert ModbusAdapter.plugin_name == "Modbus (TCP/RTU)"
    assert "registers" in ModbusAdapter.config_schema


# ---- real end-to-end read against a real (local) Modbus TCP server ----------------
# The strongest verification available without physical hardware: this runs the actual
# Modbus wire protocol over a real socket against pymodbus's own server implementation,
# not a mock — so it exercises this adapter's real network I/O path, not just its decode
# math (already covered above).


def _make_server(values: list[int], port: int) -> ModbusTcpServer:
    # ModbusSequentialDataBlock's start address is 1-indexed internally (address 1 ->
    # wire/client address 0) — this is this pymodbus version's own datastore
    # convention, unrelated to this adapter's `registers[].address` field, which is a
    # plain 0-based wire address matching what read_holding_registers actually sends.
    # This datastore API is deprecated in pymodbus 3.14 (in favor of SimData/SimDevice)
    # but still functional and simpler for a fixed, values-known-upfront test fixture —
    # no runtime mutation needed here, so the deprecated-but-working shim is fine.
    holding_registers = ModbusSequentialDataBlock(1, values)
    device_context = ModbusDeviceContext(hr=holding_registers)
    server_context = ModbusServerContext(devices=device_context, single=True)
    return ModbusTcpServer(server_context, address=("127.0.0.1", port))


async def test_read_multiple_registers_from_a_real_server():
    float_hi, float_lo = struct.unpack(">HH", struct.pack(">f", 12.34))
    int32_hi, int32_lo = struct.unpack(">HH", struct.pack(">i", -1000))
    register_values = [
        850,  # address 0: int16, scale 0.1 -> 85.0
        65486,  # address 1: int16, scale 0.1 -> -5.0 (negative, two's complement)
        float_hi, float_lo,  # address 2-3: float32
        int32_hi, int32_lo,  # address 4-5: int32
    ]
    server = _make_server(register_values, TEST_PORT)
    await server.serve_forever(background=True)
    try:
        room = make_room(
            transport="tcp",
            host="127.0.0.1",
            port=TEST_PORT,
            registers=[
                {"metric": "temp_f", "address": 0, "data_type": "int16", "scale": 0.1},
                {"metric": "below_freezing", "address": 1, "data_type": "int16", "scale": 0.1},
                {"metric": "co2_ppm", "address": 2, "data_type": "float32"},
                {"metric": "counter", "address": 4, "data_type": "int32"},
            ],
        )
        adapter = ModbusAdapter()
        values = await adapter.read(room)

        assert values["temp_f"] == pytest.approx(85.0)
        assert values["below_freezing"] == pytest.approx(-5.0)
        assert values["co2_ppm"] == pytest.approx(12.34, abs=1e-3)
        assert values["counter"] == pytest.approx(-1000.0)
    finally:
        for client in adapter._clients.values():
            client.close()
        await server.shutdown()


async def test_two_rooms_on_same_target_share_one_connection():
    port = TEST_PORT + 1
    server = _make_server([700], port)
    await server.serve_forever(background=True)
    try:
        config = {
            "transport": "tcp", "host": "127.0.0.1", "port": port,
            "registers": [{"metric": "temp_f", "address": 0, "data_type": "int16", "scale": 0.1}],
        }
        adapter = ModbusAdapter()
        await adapter.read(make_room(**config))
        await adapter.read(make_room(**config))
        # Same (transport, host, port) key -> same cached client instance, not a fresh one per call
        assert len(adapter._clients) == 1
    finally:
        for client in adapter._clients.values():
            client.close()
        await server.shutdown()


async def test_connecting_to_nothing_raises_a_clear_error():
    adapter = ModbusAdapter()
    room = make_room(
        transport="tcp", host="127.0.0.1", port=1,  # nothing listens on port 1
        registers=[{"metric": "x", "address": 0}],
    )
    with pytest.raises(RuntimeError, match="could not connect"):
        await adapter.read(room)
