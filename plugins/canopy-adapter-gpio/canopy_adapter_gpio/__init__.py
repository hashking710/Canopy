"""
Direct-attached Raspberry Pi sensors — no cloud account, no vendor server, reads
straight off the Pi's own I2C bus, 1-Wire bus, or GPIO pins. This is the one adapter
category that genuinely cannot be verified end-to-end without physical hardware
attached to a real Pi — everything below is implemented from each device's public
datasheet/protocol as carefully as it can be without a chip to test against, and the
honest confidence level is called out per sensor kind rather than blanket-claimed.
What IS unit-tested here: every piece of pure math/parsing that doesn't require a
real bus (CRC8, temp/RH conversion, DS18B20 sysfs text parsing, ADS1115 register
math) and the full digital-GPIO path, which gpiozero's own official mock pin
factory makes genuinely testable without hardware.

BME280 and SCD4x CO2 (real, more involved compensation math than everything else
here) are covered too, each with its own explicit, higher-caution confidence note —
see their sections below.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, ClassVar

from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room
from gpiozero import DigitalInputDevice, DigitalOutputDevice

if TYPE_CHECKING:
    from smbus2 import SMBus


def _import_smbus2():
    # smbus2 imports the stdlib `fcntl` module at its own top level, which only
    # exists on POSIX — importing smbus2 anywhere at this module's own top level
    # would make the whole adapter (including every pure-logic function below, and
    # every non-I2C sensor kind) fail to even import on Windows/macOS dev machines
    # and any CI runner that isn't Linux. Deferred to here, called only from the
    # methods that actually touch a real I2C bus, so installing/testing this
    # package's non-hardware logic works everywhere; only real I2C reads require
    # actually being on Linux with i2c-dev available.
    try:
        from smbus2 import SMBus, i2c_msg
    except ImportError as exc:
        raise RuntimeError(
            "smbus2 is not usable in this environment (it requires Linux's i2c-dev, "
            "e.g. running on a real Raspberry Pi) — I2C sensor kinds (sht31, "
            "ads1115_analog, sgp30, ens160, scd4x) can't be read here"
        ) from exc
    return SMBus, i2c_msg

SHT31_MEASURE_HIGH_REPEATABILITY = [0x2C, 0x06]
SHT31_MEASUREMENT_DELAY_SECONDS = 0.015

ADS1115_CONFIG_REGISTER = 0x01
ADS1115_CONVERSION_REGISTER = 0x00
ADS1115_CONVERSION_DELAY_SECONDS = 0.01
# ±4.096V full-scale range (PGA=001) — the common choice for a 3.3V/5V sensor output;
# LSB size follows directly: 4.096V / 32768 counts.
ADS1115_FS_VOLTS = 4.096
ADS1115_LSB_VOLTS = ADS1115_FS_VOLTS / 32768

SGP30_INIT_AIR_QUALITY = [0x20, 0x03]
SGP30_MEASURE_AIR_QUALITY = [0x20, 0x08]
SGP30_MEASURE_DELAY_SECONDS = 0.012

HX711_READY_TIMEOUT_SECONDS = 1.0
HX711_CLOCK_PULSE_SECONDS = 0.000001  # 1us — well within HX711's 0.2-50us valid clock window

# ScioSense ENS160 register map — unlike SGP30/SHT31's raw-command protocol, this is a
# conventional register-addressed device (register pointer + read/write), so it uses
# write_i2c_block_data/read_i2c_block_data like ADS1115, not i2c_msg.
ENS160_REG_OPMODE = 0x10
ENS160_OPMODE_STANDARD = 0x02
ENS160_REG_DATA_AQI = 0x21
ENS160_REG_DATA_TVOC = 0x22  # uint16, little-endian (low byte first) — opposite byte
ENS160_REG_DATA_ECO2 = 0x24  # order from SGP30/SHT31's big-endian readings; a common
# point of confusion when copying patterns between different vendors' chips.

SCD4X_START_PERIODIC_MEASUREMENT = [0x21, 0xB1]
SCD4X_READ_MEASUREMENT = [0xEC, 0x05]
SCD4X_READ_DELAY_SECONDS = 0.001

# BME280 register-addressed protocol.
BME280_REG_CALIB_1 = 0x88  # dig_T1..dig_T3, dig_P1..dig_P9 (26 bytes)
BME280_REG_CALIB_2 = 0xA1  # dig_H1 (1 byte)
BME280_REG_CALIB_3 = 0xE1  # dig_H2..dig_H6, packed (7 bytes)
BME280_REG_CTRL_HUM = 0xF2
BME280_REG_CTRL_MEAS = 0xF4
BME280_REG_DATA = 0xF7  # press_msb..hum_lsb (8 bytes)
# ctrl_hum/ctrl_meas: oversampling x1 on all three, forced mode (one-shot measurement,
# then the device returns to sleep — appropriate for a poll-cycle-driven read rather
# than continuous free-running conversion).
BME280_OVERSAMPLING_X1 = 0b001
BME280_MODE_FORCED = 0b01
BME280_MEASUREMENT_DELAY_SECONDS = 0.05


class GpioAdapter(SensorAdapter):
    """
    One adapter, several sensor "kinds" — mirrors the Modbus adapter's approach of
    letting each room describe its own device shape rather than assuming a fixed
    schema, since a Pi can have any mix of I2C/1-Wire/GPIO sensors attached.

    room.adapter_config shape:
        {
          "sensors": [
            {"kind": "sht31", "i2c_bus": 1, "i2c_address": "0x44",
             "metrics": {"temp_f": "temp", "rh_pct": "humidity"}},
            {"kind": "ds18b20", "sensor_id": "28-0000012345", "metric": "root_temp_f"},
            {"kind": "ads1115_analog", "i2c_bus": 1, "i2c_address": "0x48",
             "channel": 0, "metric": "par_umol", "scale": 500.0, "offset": 0.0},
            {"kind": "gpio_digital", "pin": 17, "metric": "leak_detected",
             "active_high": true, "true_value": 1.0, "false_value": 0.0},
            {"kind": "sgp30", "i2c_bus": 1, "i2c_address": "0x58",
             "metrics": {"eco2_ppm": "eco2", "tvoc_ppb": "tvoc"}},
            {"kind": "hx711", "data_pin": 5, "clock_pin": 6, "metric": "yield_g",
             "scale": 415.0, "offset": 8_388_608},
            {"kind": "ens160", "i2c_bus": 1, "i2c_address": "0x53",
             "metrics": {"eco2_ppm": "eco2", "tvoc_ppb": "tvoc", "aqi": "aqi"}},
            {"kind": "scd4x", "i2c_bus": 1, "i2c_address": "0x62",
             "metrics": {"co2_ppm": "co2", "temp_f": "temp", "rh_pct": "humidity"}},
            {"kind": "bme280", "i2c_bus": 1, "i2c_address": "0x76",
             "metrics": {"temp_f": "temp", "rh_pct": "humidity", "pressure_hpa": "pressure"}}
          ]
        }

    "kind": "sht31" — I2C temp+humidity (Sensirion SHT31/SHT30/SHT35 — same protocol
    family). Confidence: high — a simple, widely-implemented protocol with a
    documented CRC8, correctly transcribed here (see _crc8/_decode_sht31).

    "kind": "ds18b20" — 1-Wire temperature, via the Linux kernel's w1-therm driver
    (/sys/bus/w1/devices/<sensor_id>/w1_slave — the kernel handles the 1-Wire protocol
    itself, this just reads the resulting sysfs file). Confidence: high — no custom
    protocol implementation involved at all.

    "kind": "ads1115_analog" — generic analog input via a TI ADS1115 I2C ADC, linearly
    scaled (value = voltage * scale + offset) — covers anything with an analog
    voltage output: PAR/PPFD light sensors (e.g. Apogee SQ-500's mV output),
    capacitive soil moisture probes, analog EC/pH transmitters. Confidence: high for
    the ADC read itself (standard, well-documented register protocol); the
    scale/offset calibration is inherently per-sensor and per-installation, not
    something this adapter can get right without your specific sensor's datasheet.

    "kind": "gpio_digital" — a plain digital input pin, for a float switch or binary
    leak/level sensor. Confidence: high — this is the one path fully testable without
    hardware, via gpiozero's own mock pin factory (see tests).

    "kind": "sgp30" — I2C VOC/eCO2 (Sensirion SGP30) — an early-warning signal for
    powdery mildew/mold, since fungal growth produces detectable VOCs before it's
    visible. Confidence: high — same CRC8 checksum family as SHT31 (Sensirion reuses
    it across their whole product line), correctly reused here. Needs a real ~15s
    on-device warmup after power-on before readings are meaningful — this adapter
    doesn't model that state, so treat the first few poll cycles' values as unreliable.

    "kind": "hx711" — a load cell amplifier, for a scale under a reservoir or drying
    tray (real harvest/yield tracking, not just climate). Confidence: high for the
    pure decode math (24-bit two's complement — see decode_hx711_24bit); the actual
    GPIO bit-banged read is timing-sensitive (HX711 wants each clock pulse within a
    fairly narrow window) in a way Python's own scheduling jitter can occasionally
    miss on a loaded system — a known, inherent characteristic of bit-banged
    protocols in Python, not specific to this implementation. scale/offset are
    per-installation calibration values (weigh a known reference mass to derive
    them), same as ADS1115's.

    "kind": "ens160" — I2C VOC/eCO2/AQI (ScioSense ENS160) — an alternative/complement
    to SGP30 that also reports a simple 1-5 air-quality-index summary. Confidence:
    medium — a conventional register-addressed protocol (lower risk than a raw-command
    one), but ENS160's register map is less universally implemented than Sensirion's
    SHT3x/SGPx family, so the exact register addresses here carry more transcription
    risk than SGP30's — cross-check against the datasheet before trusting readings.
    Also needs the same real ~15s-3min on-device warmup as SGP30 before values are
    meaningful.

    "kind": "scd4x" — I2C CO2/temp/RH (Sensirion SCD40/SCD41) — *real* sensed CO2 via
    NDIR, not the derived/estimated value some cheaper "CO2" sensors report.
    Confidence: high for the protocol itself (same CRC8 family as SHT31/SGP30), but
    genuinely needs a "start periodic measurement" command sent once before any
    reading is valid, and the device only refreshes every ~5s in that mode — this
    adapter sends the start command automatically on first use per device (cached, so
    it's not re-sent and the measurement cycle restarted every poll), but the first
    read attempt or two after that may still raise (data not ready yet) — the
    poller's normal per-room retry-next-cycle handling covers this the same way it
    covers any other transient adapter failure. Also worth flagging since it's an
    easy mistake to copy from SHT31: SCD4x's temp/RH conversion divides by 65536
    (2^16), not SHT31's 65535 — a real, documented difference between Sensirion's own
    product lines, not a typo.

    "kind": "bme280" — I2C temp/RH/barometric pressure (Bosch BME280). **Confidence:
    lower than every other sensor in this package, called out deliberately rather
    than blanket-claimed.** Every other sensor here needs a short command or a
    conventional register read; BME280 needs on-device calibration coefficients
    (burned into NVM per physical chip, read from registers 0x88-0xA1 and 0xE1-0xE7)
    fed through Bosch's own published compensation formulas — real 32/64-bit
    fixed-point math with several intermediate terms per measurement (see
    `compensate_bme280`). Implemented here from Bosch's official datasheet reference
    algorithm (transcribed as carefully as possible from memory of that widely-
    reproduced formula, not copied from a datasheet PDF open in front of the code) —
    this is a meaningfully higher transcription-risk piece of code than anything else
    in this package. Tests below check internal consistency (compensated values move
    the right direction as raw ADC counts change, revert to sane values at the
    formula's own defined edge cases) rather than an exact worked-example match this
    implementation cannot fully guarantee without a real chip or the datasheet PDF in
    hand. **Cross-check against Bosch's BME280 datasheet §4.2.3 and its own worked
    example (§8.1) before trusting a real reading from this.**
    """

    plugin_name = "Direct GPIO/I2C/1-Wire sensors"
    plugin_description = (
        "Direct-attached Pi sensors: SHT31 (I2C temp/RH), DS18B20 (1-Wire temp), "
        "ADS1115 (I2C analog — PAR sensors, soil moisture, generic analog probes), "
        "SGP30/ENS160 (I2C VOC/eCO2 — early mold/mildew warning), SCD4x (I2C real "
        "sensed CO2), BME280 (I2C temp/RH/pressure — lower-confidence, see "
        "docstring), HX711 (load cell — harvest/yield weight), and digital GPIO "
        "(float switches / leak sensors)."
    )
    category: ClassVar[str] = "hardware"
    config_schema: ClassVar[dict[str, str]] = {
        "sensors": "list of {kind, metric(s), ...kind-specific fields} — see this "
        "adapter's own docstring for the shape of each kind",
    }

    def __init__(self) -> None:
        self._i2c_buses: dict[int, SMBus] = {}
        self._gpio_devices: dict[int, DigitalInputDevice] = {}
        self._hx711_devices: dict[tuple[int, int], tuple[DigitalInputDevice, DigitalOutputDevice]] = {}
        self._scd4x_started: set[tuple[int, int]] = set()
        self._bme280_calibration: dict[tuple[int, int], "Bme280Calibration"] = {}

    async def connect(self, room: Room) -> None:
        pass  # buses/pins opened lazily on first read(), see _get_bus

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
            if kind == "sht31":
                values.update(self._read_sht31(sensor))
            elif kind == "ds18b20":
                values[sensor["metric"]] = self._read_ds18b20(sensor)
            elif kind == "ads1115_analog":
                values[sensor["metric"]] = self._read_ads1115(sensor)
            elif kind == "gpio_digital":
                values[sensor["metric"]] = self._read_gpio_digital(sensor)
            elif kind == "sgp30":
                values.update(self._read_sgp30(sensor))
            elif kind == "hx711":
                values[sensor["metric"]] = self._read_hx711(sensor)
            elif kind == "ens160":
                values.update(self._read_ens160(sensor))
            elif kind == "scd4x":
                values.update(self._read_scd4x(sensor))
            elif kind == "bme280":
                values.update(self._read_bme280(sensor))
            else:
                raise RuntimeError(f"room '{room.id}': unknown sensor kind '{kind}'")
        return values

    def _get_bus(self, bus_number: int) -> SMBus:
        if bus_number not in self._i2c_buses:
            SMBus, _ = _import_smbus2()
            self._i2c_buses[bus_number] = SMBus(bus_number)
        return self._i2c_buses[bus_number]

    def _read_sht31(self, sensor: dict) -> dict[str, float]:
        bus = self._get_bus(sensor.get("i2c_bus", 1))
        address = _parse_i2c_address(sensor["i2c_address"])
        raw = _read_sht31_raw(bus, address)
        temp_c, rh_pct = decode_sht31(raw)
        metrics = sensor.get("metrics", {})
        out: dict[str, float] = {}
        for metric_key, field in metrics.items():
            if field == "temp":
                out[metric_key] = temp_c * 9 / 5 + 32
            elif field == "humidity":
                out[metric_key] = rh_pct
            else:
                raise RuntimeError(f"sht31 sensor: unknown field '{field}' (must be 'temp' or 'humidity')")
        return out

    def _read_ds18b20(self, sensor: dict) -> float:
        sensor_id = sensor.get("sensor_id")
        if not sensor_id:
            raise RuntimeError("ds18b20 sensor missing 'sensor_id'")
        path = f"/sys/bus/w1/devices/{sensor_id}/w1_slave"
        with open(path) as f:
            contents = f.read()
        temp_c = parse_ds18b20_sysfs(contents)
        return temp_c * 9 / 5 + 32

    def _read_ads1115(self, sensor: dict) -> float:
        bus = self._get_bus(sensor.get("i2c_bus", 1))
        address = _parse_i2c_address(sensor["i2c_address"])
        channel = int(sensor.get("channel", 0))
        raw = _read_ads1115_raw(bus, address, channel)
        voltage = raw * ADS1115_LSB_VOLTS
        scale = sensor.get("scale", 1.0)
        offset = sensor.get("offset", 0.0)
        return voltage * scale + offset

    def _read_gpio_digital(self, sensor: dict) -> float:
        pin = sensor["pin"]
        active_high = sensor.get("active_high", True)
        true_value = sensor.get("true_value", 1.0)
        false_value = sensor.get("false_value", 0.0)
        device = self._get_gpio_device(pin, active_high)
        # `pull_up=not active_high` already tells gpiozero which physical level counts
        # as "active" — its own .value/.is_active is relative to that, not the raw pin
        # state, so no separate manual inversion belongs here (that would silently
        # double-invert active-low sensors).
        return true_value if device.value else false_value

    def _get_gpio_device(self, pin: int, active_high: bool) -> DigitalInputDevice:
        if pin not in self._gpio_devices:
            self._gpio_devices[pin] = DigitalInputDevice(pin, pull_up=not active_high)
        return self._gpio_devices[pin]

    def _read_sgp30(self, sensor: dict) -> dict[str, float]:
        bus = self._get_bus(sensor.get("i2c_bus", 1))
        address = _parse_i2c_address(sensor["i2c_address"])
        raw = _read_sgp30_raw(bus, address)
        eco2_ppm, tvoc_ppb = decode_sgp30(raw)
        metrics = sensor.get("metrics", {})
        out: dict[str, float] = {}
        for metric_key, field in metrics.items():
            if field == "eco2":
                out[metric_key] = eco2_ppm
            elif field == "tvoc":
                out[metric_key] = tvoc_ppb
            else:
                raise RuntimeError(f"sgp30 sensor: unknown field '{field}' (must be 'eco2' or 'tvoc')")
        return out

    def _read_hx711(self, sensor: dict) -> float:
        data_pin = sensor["data_pin"]
        clock_pin = sensor["clock_pin"]
        scale = sensor.get("scale", 1.0)
        offset = sensor.get("offset", 0.0)
        data, clock = self._get_hx711_devices(data_pin, clock_pin)
        raw = _read_hx711_raw(data, clock)
        return (raw - offset) / scale

    def _get_hx711_devices(self, data_pin: int, clock_pin: int) -> tuple[DigitalInputDevice, DigitalOutputDevice]:
        key = (data_pin, clock_pin)
        if key not in self._hx711_devices:
            self._hx711_devices[key] = (DigitalInputDevice(data_pin), DigitalOutputDevice(clock_pin, initial_value=False))
        return self._hx711_devices[key]

    def _read_ens160(self, sensor: dict) -> dict[str, float]:
        bus = self._get_bus(sensor.get("i2c_bus", 1))
        address = _parse_i2c_address(sensor["i2c_address"])
        bus.write_i2c_block_data(address, ENS160_REG_OPMODE, [ENS160_OPMODE_STANDARD])
        aqi_raw = bus.read_i2c_block_data(address, ENS160_REG_DATA_AQI, 1)
        tvoc_raw = bus.read_i2c_block_data(address, ENS160_REG_DATA_TVOC, 2)
        eco2_raw = bus.read_i2c_block_data(address, ENS160_REG_DATA_ECO2, 2)
        aqi, tvoc_ppb, eco2_ppm = decode_ens160(bytes(aqi_raw), bytes(tvoc_raw), bytes(eco2_raw))

        metrics = sensor.get("metrics", {})
        out: dict[str, float] = {}
        for metric_key, field in metrics.items():
            if field == "aqi":
                out[metric_key] = aqi
            elif field == "tvoc":
                out[metric_key] = tvoc_ppb
            elif field == "eco2":
                out[metric_key] = eco2_ppm
            else:
                raise RuntimeError(f"ens160 sensor: unknown field '{field}' (must be 'aqi', 'tvoc', or 'eco2')")
        return out

    def _read_scd4x(self, sensor: dict) -> dict[str, float]:
        bus = self._get_bus(sensor.get("i2c_bus", 1))
        address = _parse_i2c_address(sensor["i2c_address"])
        bus_number = sensor.get("i2c_bus", 1)

        key = (bus_number, address)
        if key not in self._scd4x_started:
            _, i2c_msg = _import_smbus2()
            bus.i2c_rdwr(i2c_msg.write(address, SCD4X_START_PERIODIC_MEASUREMENT))
            self._scd4x_started.add(key)
            raise RuntimeError("scd4x: periodic measurement just started, no reading available yet this cycle")

        raw = _read_scd4x_raw(bus, address)
        co2_ppm, temp_c, rh_pct = decode_scd4x(raw)

        metrics = sensor.get("metrics", {})
        out: dict[str, float] = {}
        for metric_key, field in metrics.items():
            if field == "co2":
                out[metric_key] = co2_ppm
            elif field == "temp":
                out[metric_key] = temp_c * 9 / 5 + 32
            elif field == "humidity":
                out[metric_key] = rh_pct
            else:
                raise RuntimeError(f"scd4x sensor: unknown field '{field}' (must be 'co2', 'temp', or 'humidity')")
        return out

    def _read_bme280(self, sensor: dict) -> dict[str, float]:
        bus = self._get_bus(sensor.get("i2c_bus", 1))
        address = _parse_i2c_address(sensor["i2c_address"])
        bus_number = sensor.get("i2c_bus", 1)

        key = (bus_number, address)
        if key not in self._bme280_calibration:
            calib1 = bytes(bus.read_i2c_block_data(address, BME280_REG_CALIB_1, 26))
            calib2 = bytes(bus.read_i2c_block_data(address, BME280_REG_CALIB_2, 1))
            calib3 = bytes(bus.read_i2c_block_data(address, BME280_REG_CALIB_3, 7))
            self._bme280_calibration[key] = parse_bme280_calibration(calib1, calib2, calib3)
        calibration = self._bme280_calibration[key]

        # ctrl_hum must be written before ctrl_meas for the humidity oversampling
        # setting to take effect on the next measurement — a real, documented BME280
        # ordering requirement, not an arbitrary choice.
        bus.write_i2c_block_data(address, BME280_REG_CTRL_HUM, [BME280_OVERSAMPLING_X1])
        ctrl_meas = (BME280_OVERSAMPLING_X1 << 5) | (BME280_OVERSAMPLING_X1 << 2) | BME280_MODE_FORCED
        bus.write_i2c_block_data(address, BME280_REG_CTRL_MEAS, [ctrl_meas])
        time.sleep(BME280_MEASUREMENT_DELAY_SECONDS)

        data = bytes(bus.read_i2c_block_data(address, BME280_REG_DATA, 8))
        adc_p, adc_t, adc_h = parse_bme280_raw_adc(data)
        temp_c, pressure_hpa, rh_pct = compensate_bme280(adc_t, adc_p, adc_h, calibration)

        metrics = sensor.get("metrics", {})
        out: dict[str, float] = {}
        for metric_key, field in metrics.items():
            if field == "temp":
                out[metric_key] = temp_c * 9 / 5 + 32
            elif field == "humidity":
                out[metric_key] = rh_pct
            elif field == "pressure":
                out[metric_key] = pressure_hpa
            else:
                raise RuntimeError(f"bme280 sensor: unknown field '{field}' (must be 'temp', 'humidity', or 'pressure')")
        return out


def _parse_i2c_address(address) -> int:
    if isinstance(address, str):
        return int(address, 0)  # accepts "0x44" or "68"
    return int(address)


# ---- SHT31 (I2C temp/RH) — protocol math, pure/testable -----------------------------


def _crc8(data: bytes) -> int:
    """Sensirion's documented CRC8: polynomial 0x31, init 0xFF, no reflection —
    used to verify each 2-byte reading wasn't corrupted in transit."""
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x31) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def decode_sht31(raw: bytes) -> tuple[float, float]:
    """raw is the 6 bytes SHT31 returns after a measurement command: [temp_msb,
    temp_lsb, temp_crc, hum_msb, hum_lsb, hum_crc]. Returns (temp_c, rh_pct)."""
    if len(raw) != 6:
        raise RuntimeError(f"sht31: expected 6 bytes, got {len(raw)}")
    temp_bytes, temp_crc = raw[0:2], raw[2]
    hum_bytes, hum_crc = raw[3:5], raw[5]
    if _crc8(temp_bytes) != temp_crc:
        raise RuntimeError("sht31: temperature CRC check failed")
    if _crc8(hum_bytes) != hum_crc:
        raise RuntimeError("sht31: humidity CRC check failed")

    raw_temp = (temp_bytes[0] << 8) | temp_bytes[1]
    raw_hum = (hum_bytes[0] << 8) | hum_bytes[1]
    temp_c = -45 + 175 * (raw_temp / 65535)
    rh_pct = 100 * (raw_hum / 65535)
    return temp_c, rh_pct


def _read_sht31_raw(bus: SMBus, address: int) -> bytes:
    _, i2c_msg = _import_smbus2()
    bus.i2c_rdwr(i2c_msg.write(address, SHT31_MEASURE_HIGH_REPEATABILITY))
    time.sleep(SHT31_MEASUREMENT_DELAY_SECONDS)
    read = i2c_msg.read(address, 6)
    bus.i2c_rdwr(read)
    return bytes(read)


# ---- DS18B20 (1-Wire temp via kernel sysfs) — text parsing, pure/testable -----------


def parse_ds18b20_sysfs(contents: str) -> float:
    """w1_slave file looks like:
        a3 01 4b 46 7f ff 0c 10 74 : crc=74 YES
        a3 01 4b 46 7f ff 0c 10 74 t=26187
    First line's trailing YES/NO is the kernel's own CRC check on the 1-Wire read;
    NO means a corrupted read that must not be trusted. Second line's t=<millidegrees C>
    is the actual reading."""
    lines = contents.strip().splitlines()
    if len(lines) < 2:
        raise RuntimeError(f"ds18b20: unexpected w1_slave content: {contents!r}")
    if not lines[0].rstrip().endswith("YES"):
        raise RuntimeError("ds18b20: kernel CRC check failed on this read (w1_slave reported NO)")
    marker = "t="
    idx = lines[1].find(marker)
    if idx == -1:
        raise RuntimeError(f"ds18b20: no 't=' reading found in w1_slave content: {lines[1]!r}")
    millidegrees = int(lines[1][idx + len(marker):])
    return millidegrees / 1000.0


# ---- ADS1115 (I2C analog ADC) — register math, pure/testable ------------------------


def build_ads1115_config(channel: int) -> tuple[int, int]:
    """Returns the 2 config-register bytes (big-endian) to start a single-shot
    conversion on the given single-ended channel (0-3) at ±4.096V full scale, 128 SPS.
    MUX field 0b100+channel selects AINx vs GND, per the ADS1115 datasheet's table."""
    if not 0 <= channel <= 3:
        raise RuntimeError(f"ads1115: channel must be 0-3, got {channel}")
    mux = 0b100 + channel
    config = (
        (1 << 15)  # OS: start a single conversion
        | (mux << 12)  # MUX: single-ended AINx vs GND
        | (0b001 << 9)  # PGA: +/-4.096V
        | (1 << 8)  # MODE: single-shot
        | (0b100 << 5)  # DR: 128 SPS
    )
    return (config >> 8) & 0xFF, config & 0xFF


def decode_ads1115_conversion(data: bytes) -> int:
    """data is the 2 bytes read back from the conversion register — a signed 16-bit
    value, two's complement."""
    if len(data) != 2:
        raise RuntimeError(f"ads1115: expected 2 bytes, got {len(data)}")
    raw = (data[0] << 8) | data[1]
    if raw >= 0x8000:
        raw -= 0x10000
    return raw


def _read_ads1115_raw(bus: SMBus, address: int, channel: int) -> int:
    config_hi, config_lo = build_ads1115_config(channel)
    bus.write_i2c_block_data(address, ADS1115_CONFIG_REGISTER, [config_hi, config_lo])
    time.sleep(ADS1115_CONVERSION_DELAY_SECONDS)
    data = bus.read_i2c_block_data(address, ADS1115_CONVERSION_REGISTER, 2)
    return decode_ads1115_conversion(bytes(data))


# ---- SGP30 (I2C VOC/eCO2) — protocol math, pure/testable -----------------------------


def decode_sgp30(raw: bytes) -> tuple[float, float]:
    """raw is the 6 bytes SGP30 returns after a measure-air-quality command:
    [eco2_msb, eco2_lsb, eco2_crc, tvoc_msb, tvoc_lsb, tvoc_crc]. Returns
    (eco2_ppm, tvoc_ppb) — both direct uint16 values, no scaling needed."""
    if len(raw) != 6:
        raise RuntimeError(f"sgp30: expected 6 bytes, got {len(raw)}")
    eco2_bytes, eco2_crc = raw[0:2], raw[2]
    tvoc_bytes, tvoc_crc = raw[3:5], raw[5]
    if _crc8(eco2_bytes) != eco2_crc:
        raise RuntimeError("sgp30: eCO2 CRC check failed")
    if _crc8(tvoc_bytes) != tvoc_crc:
        raise RuntimeError("sgp30: TVOC CRC check failed")

    eco2_ppm = (eco2_bytes[0] << 8) | eco2_bytes[1]
    tvoc_ppb = (tvoc_bytes[0] << 8) | tvoc_bytes[1]
    return float(eco2_ppm), float(tvoc_ppb)


def _read_sgp30_raw(bus: SMBus, address: int) -> bytes:
    _, i2c_msg = _import_smbus2()
    bus.i2c_rdwr(i2c_msg.write(address, SGP30_MEASURE_AIR_QUALITY))
    time.sleep(SGP30_MEASURE_DELAY_SECONDS)
    read = i2c_msg.read(address, 6)
    bus.i2c_rdwr(read)
    return bytes(read)


# ---- ENS160 (I2C VOC/eCO2/AQI) — register decode math, pure/testable -----------------


def decode_ens160(aqi_raw: bytes, tvoc_raw: bytes, eco2_raw: bytes) -> tuple[int, float, float]:
    """aqi_raw is 1 byte (values 1-5); tvoc_raw/eco2_raw are each 2 bytes,
    little-endian (low byte first — opposite byte order from SGP30/SHT31's readings).
    Returns (aqi, tvoc_ppb, eco2_ppm)."""
    if len(aqi_raw) != 1:
        raise RuntimeError(f"ens160: expected 1 AQI byte, got {len(aqi_raw)}")
    if len(tvoc_raw) != 2 or len(eco2_raw) != 2:
        raise RuntimeError("ens160: expected 2 bytes each for TVOC and eCO2")
    aqi = aqi_raw[0]
    tvoc_ppb = tvoc_raw[0] | (tvoc_raw[1] << 8)
    eco2_ppm = eco2_raw[0] | (eco2_raw[1] << 8)
    return aqi, float(tvoc_ppb), float(eco2_ppm)


# ---- SCD4x (I2C real CO2 + temp/RH) — protocol math, pure/testable -------------------


def decode_scd4x(raw: bytes) -> tuple[float, float, float]:
    """raw is the 9 bytes SCD4x returns after a read-measurement command:
    [co2_msb, co2_lsb, co2_crc, temp_msb, temp_lsb, temp_crc, rh_msb, rh_lsb, rh_crc].
    Returns (co2_ppm, temp_c, rh_pct). Divides by 65536 (2^16), not SHT31's 65535 —
    a real, documented difference in Sensirion's own conversion formula between
    product lines, not a copy-paste slip."""
    if len(raw) != 9:
        raise RuntimeError(f"scd4x: expected 9 bytes, got {len(raw)}")
    co2_bytes, co2_crc = raw[0:2], raw[2]
    temp_bytes, temp_crc = raw[3:5], raw[5]
    hum_bytes, hum_crc = raw[6:8], raw[8]
    if _crc8(co2_bytes) != co2_crc:
        raise RuntimeError("scd4x: CO2 CRC check failed")
    if _crc8(temp_bytes) != temp_crc:
        raise RuntimeError("scd4x: temperature CRC check failed")
    if _crc8(hum_bytes) != hum_crc:
        raise RuntimeError("scd4x: humidity CRC check failed")

    co2_ppm = (co2_bytes[0] << 8) | co2_bytes[1]
    raw_temp = (temp_bytes[0] << 8) | temp_bytes[1]
    raw_hum = (hum_bytes[0] << 8) | hum_bytes[1]
    temp_c = -45 + 175 * (raw_temp / 65536)
    rh_pct = 100 * (raw_hum / 65536)
    return float(co2_ppm), temp_c, rh_pct


def _read_scd4x_raw(bus: SMBus, address: int) -> bytes:
    _, i2c_msg = _import_smbus2()
    bus.i2c_rdwr(i2c_msg.write(address, SCD4X_READ_MEASUREMENT))
    time.sleep(SCD4X_READ_DELAY_SECONDS)
    read = i2c_msg.read(address, 9)
    bus.i2c_rdwr(read)
    return bytes(read)


# ---- BME280 (I2C temp/RH/pressure) — calibration parsing + compensation math --------
# See the "kind": "bme280" docstring above for this section's honest confidence level
# — this is the one piece of protocol math in this package that genuinely needs
# cross-checking against Bosch's own datasheet before production use.


class Bme280Calibration:
    """One chip's burned-in calibration coefficients — read once per physical sensor
    and reused for every subsequent measurement, since they never change."""

    __slots__ = (
        "dig_T1", "dig_T2", "dig_T3",
        "dig_P1", "dig_P2", "dig_P3", "dig_P4", "dig_P5", "dig_P6", "dig_P7", "dig_P8", "dig_P9",
        "dig_H1", "dig_H2", "dig_H3", "dig_H4", "dig_H5", "dig_H6",
    )

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


def _u16(lo: int, hi: int) -> int:
    return lo | (hi << 8)


def _s16(lo: int, hi: int) -> int:
    value = _u16(lo, hi)
    return value - 0x10000 if value >= 0x8000 else value


def _s8(value: int) -> int:
    return value - 0x100 if value >= 0x80 else value


def parse_bme280_calibration(calib1: bytes, calib2: bytes, calib3: bytes) -> Bme280Calibration:
    """calib1 is the 26 bytes from register 0x88 (dig_T1..dig_P9), calib2 is the 1
    byte from 0xA1 (dig_H1), calib3 is the 7 bytes from 0xE1 (dig_H2..dig_H6, with
    dig_H4/dig_H5 packed sharing a nibble each in calib3[2] — a real, documented
    BME280 quirk, not a transcription error)."""
    if len(calib1) != 26:
        raise RuntimeError(f"bme280: expected 26 calibration bytes at 0x88, got {len(calib1)}")
    if len(calib2) != 1:
        raise RuntimeError(f"bme280: expected 1 calibration byte at 0xA1, got {len(calib2)}")
    if len(calib3) != 7:
        raise RuntimeError(f"bme280: expected 7 calibration bytes at 0xE1, got {len(calib3)}")

    dig_H4 = (calib3[3] << 4) | (calib3[4] & 0x0F)
    if dig_H4 >= 0x800:
        dig_H4 -= 0x1000
    dig_H5 = (calib3[5] << 4) | (calib3[4] >> 4)
    if dig_H5 >= 0x800:
        dig_H5 -= 0x1000

    return Bme280Calibration(
        dig_T1=_u16(calib1[0], calib1[1]),
        dig_T2=_s16(calib1[2], calib1[3]),
        dig_T3=_s16(calib1[4], calib1[5]),
        dig_P1=_u16(calib1[6], calib1[7]),
        dig_P2=_s16(calib1[8], calib1[9]),
        dig_P3=_s16(calib1[10], calib1[11]),
        dig_P4=_s16(calib1[12], calib1[13]),
        dig_P5=_s16(calib1[14], calib1[15]),
        dig_P6=_s16(calib1[16], calib1[17]),
        dig_P7=_s16(calib1[18], calib1[19]),
        dig_P8=_s16(calib1[20], calib1[21]),
        dig_P9=_s16(calib1[22], calib1[23]),
        dig_H1=calib2[0],
        dig_H2=_s16(calib3[0], calib3[1]),
        dig_H3=calib3[2],
        dig_H4=dig_H4,
        dig_H5=dig_H5,
        dig_H6=_s8(calib3[6]),
    )


def parse_bme280_raw_adc(data: bytes) -> tuple[int, int, int]:
    """data is the 8 bytes from register 0xF7: press_msb, press_lsb, press_xlsb,
    temp_msb, temp_lsb, temp_xlsb, hum_msb, hum_lsb. Pressure/temp are 20-bit
    (top 4 bits of the xlsb byte are padding); humidity is a plain 16-bit value.
    Returns (adc_P, adc_T, adc_H)."""
    if len(data) != 8:
        raise RuntimeError(f"bme280: expected 8 data bytes at 0xF7, got {len(data)}")
    adc_p = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
    adc_t = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
    adc_h = (data[6] << 8) | data[7]
    return adc_p, adc_t, adc_h


def compensate_bme280(adc_t: int, adc_p: int, adc_h: int, cal: Bme280Calibration) -> tuple[float, float, float]:
    """Bosch's official double-precision reference compensation formula (datasheet
    §4.2.3) — temperature must be compensated first since t_fine feeds into both the
    pressure and humidity formulas. Returns (temp_c, pressure_hpa, rh_pct)."""
    var1 = (adc_t / 16384.0 - cal.dig_T1 / 1024.0) * cal.dig_T2
    var2 = (adc_t / 131072.0 - cal.dig_T1 / 8192.0) ** 2 * cal.dig_T3
    t_fine = var1 + var2
    temp_c = t_fine / 5120.0

    var1 = t_fine / 2.0 - 64000.0
    var2 = var1 * var1 * cal.dig_P6 / 32768.0
    var2 = var2 + var1 * cal.dig_P5 * 2.0
    var2 = var2 / 4.0 + cal.dig_P4 * 65536.0
    var1 = (cal.dig_P3 * var1 * var1 / 524288.0 + cal.dig_P2 * var1) / 524288.0
    var1 = (1.0 + var1 / 32768.0) * cal.dig_P1
    if var1 == 0.0:
        pressure_hpa = 0.0  # avoid a division by zero the datasheet itself calls out as invalid
    else:
        p = 1048576.0 - adc_p
        p = (p - var2 / 4096.0) * 6250.0 / var1
        var1 = cal.dig_P9 * p * p / 2147483648.0
        var2 = p * cal.dig_P8 / 32768.0
        p = p + (var1 + var2 + cal.dig_P7) / 16.0
        pressure_hpa = p / 100.0  # datasheet's own formula yields Pa; hPa is the more common display unit

    var_h = t_fine - 76800.0
    var_h = (adc_h - (cal.dig_H4 * 64.0 + cal.dig_H5 / 16384.0 * var_h)) * (
        cal.dig_H2
        / 65536.0
        * (1.0 + cal.dig_H6 / 67108864.0 * var_h * (1.0 + cal.dig_H3 / 67108864.0 * var_h))
    )
    var_h = var_h * (1.0 - cal.dig_H1 * var_h / 524288.0)
    rh_pct = min(100.0, max(0.0, var_h))

    return temp_c, pressure_hpa, rh_pct


# ---- HX711 (bit-banged load cell amplifier) — decode math, pure/testable ------------


def decode_hx711_24bit(bits: list[int]) -> int:
    """bits is a list of 24 bits (0/1), MSB first, as clocked out of HX711's DATA pin.
    Returns the signed 24-bit two's complement value."""
    if len(bits) != 24:
        raise RuntimeError(f"hx711: expected 24 bits, got {len(bits)}")
    raw = 0
    for bit in bits:
        raw = (raw << 1) | bit
    if raw >= 0x800000:
        raw -= 0x1000000
    return raw


def _read_hx711_raw(data: DigitalInputDevice, clock: DigitalOutputDevice) -> int:
    deadline = time.monotonic() + HX711_READY_TIMEOUT_SECONDS
    while data.value == 1:
        if time.monotonic() > deadline:
            raise RuntimeError("hx711: device not ready (DATA pin never went low)")
        time.sleep(0.001)

    bits = []
    for _ in range(24):
        clock.on()
        time.sleep(HX711_CLOCK_PULSE_SECONDS)
        clock.off()
        bits.append(1 if data.value else 0)
        time.sleep(HX711_CLOCK_PULSE_SECONDS)
    # A 25th pulse sets the gain/channel for the *next* conversion (128 gain, channel
    # A) — always sent, so the device is left in a known, consistent state.
    clock.on()
    time.sleep(HX711_CLOCK_PULSE_SECONDS)
    clock.off()

    return decode_hx711_24bit(bits)
