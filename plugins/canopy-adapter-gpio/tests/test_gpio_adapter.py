import pytest
from canopy_adapter_gpio import (
    Bme280Calibration,
    GpioAdapter,
    build_ads1115_config,
    compensate_bme280,
    decode_ads1115_conversion,
    decode_ens160,
    decode_hx711_24bit,
    decode_scd4x,
    decode_sgp30,
    decode_sht31,
    parse_bme280_calibration,
    parse_bme280_raw_adc,
    parse_ds18b20_sysfs,
    _crc8,
)
from canopy_agent.models import Room
from gpiozero import Device
from gpiozero.pins.mock import MockFactory


def make_room(**adapter_config) -> Room:
    return Room(
        id="gpio-room", room_type="greenhouse", path="~/gpio-room",
        adapter_type="gpio", metric_config={}, adapter_config=adapter_config,
    )


# ---- SHT31 — CRC8 and decode math, pure/testable ------------------------------------


def test_crc8_matches_sensirions_own_documented_test_vector():
    # Sensirion's SHT3x datasheet/reference drivers cite checksum(0xBEEF) == 0x92 as
    # the canonical worked example for this exact CRC8 variant (poly 0x31, init 0xFF).
    assert _crc8(bytes([0xBE, 0xEF])) == 0x92


def test_decode_sht31_known_good_reading():
    # 0 raw counts -> -45C exactly; 65535 raw counts -> 130C / 100% RH exactly (the
    # documented endpoints of SHT31's linear conversion formula).
    zero_crc = _crc8(bytes([0x00, 0x00]))
    max_crc = _crc8(bytes([0xFF, 0xFF]))
    temp_c, rh_pct = decode_sht31(bytes([0x00, 0x00, zero_crc, 0xFF, 0xFF, max_crc]))
    assert temp_c == pytest.approx(-45.0)
    assert rh_pct == pytest.approx(100.0, abs=0.01)


def test_decode_sht31_bad_crc_raises():
    with pytest.raises(RuntimeError, match="CRC"):
        decode_sht31(bytes([0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF]))  # wrong CRC bytes


def test_decode_sht31_wrong_length_raises():
    with pytest.raises(RuntimeError, match="expected 6 bytes"):
        decode_sht31(bytes([0x00, 0x00]))


# ---- DS18B20 — sysfs text parsing, pure/testable -------------------------------------


def test_parse_ds18b20_sysfs_positive_temp():
    contents = "a3 01 4b 46 7f ff 0c 10 74 : crc=74 YES\na3 01 4b 46 7f ff 0c 10 74 t=26187\n"
    assert parse_ds18b20_sysfs(contents) == pytest.approx(26.187)


def test_parse_ds18b20_sysfs_negative_temp():
    contents = "some crc line : crc=74 YES\nsome data t=-5250\n"
    assert parse_ds18b20_sysfs(contents) == pytest.approx(-5.25)


def test_parse_ds18b20_sysfs_bad_crc_raises():
    contents = "a3 01 4b 46 7f ff 0c 10 74 : crc=74 NO\na3 01 4b 46 7f ff 0c 10 74 t=26187\n"
    with pytest.raises(RuntimeError, match="CRC check failed"):
        parse_ds18b20_sysfs(contents)


def test_parse_ds18b20_sysfs_malformed_raises():
    with pytest.raises(RuntimeError, match="no 't=' reading"):
        parse_ds18b20_sysfs("crc=74 YES\nno temperature here\n")


# ---- ADS1115 — register math, pure/testable -----------------------------------------


def test_build_ads1115_config_channel_0():
    hi, lo = build_ads1115_config(0)
    config = (hi << 8) | lo
    assert config & 0x8000  # OS bit set (start conversion)
    assert (config >> 12) & 0b111 == 0b100  # MUX = AIN0 vs GND


def test_build_ads1115_config_channel_3():
    hi, lo = build_ads1115_config(3)
    config = (hi << 8) | lo
    assert (config >> 12) & 0b111 == 0b111  # MUX = AIN3 vs GND


def test_build_ads1115_config_invalid_channel_raises():
    with pytest.raises(RuntimeError, match="channel must be 0-3"):
        build_ads1115_config(4)


def test_decode_ads1115_conversion_positive():
    assert decode_ads1115_conversion(bytes([0x40, 0x00])) == 0x4000  # 16384


def test_decode_ads1115_conversion_negative_twos_complement():
    assert decode_ads1115_conversion(bytes([0xFF, 0xFF])) == -1


def test_decode_ads1115_conversion_wrong_length_raises():
    with pytest.raises(RuntimeError, match="expected 2 bytes"):
        decode_ads1115_conversion(bytes([0x00]))


# ---- SGP30 — CRC8 (shared with SHT31) and decode math, pure/testable -----------------


def test_decode_sgp30_known_values():
    eco2_bytes = bytes([0x01, 0xF4])  # 500
    tvoc_bytes = bytes([0x00, 0x32])  # 50
    raw = eco2_bytes + bytes([_crc8(eco2_bytes)]) + tvoc_bytes + bytes([_crc8(tvoc_bytes)])
    eco2, tvoc = decode_sgp30(raw)
    assert eco2 == 500.0
    assert tvoc == 50.0


def test_decode_sgp30_bad_crc_raises():
    with pytest.raises(RuntimeError, match="CRC"):
        decode_sgp30(bytes([0x01, 0xF4, 0x00, 0x00, 0x32, 0x00]))


def test_decode_sgp30_wrong_length_raises():
    with pytest.raises(RuntimeError, match="expected 6 bytes"):
        decode_sgp30(bytes([0x01, 0xF4]))


# ---- HX711 — 24-bit two's complement decode, pure/testable ---------------------------


def test_decode_hx711_24bit_positive():
    bits = [0] + [1] * 23  # smallest positive value with bit 22 set, well below the sign bit
    assert decode_hx711_24bit(bits) == 0x7FFFFF


def test_decode_hx711_24bit_zero():
    assert decode_hx711_24bit([0] * 24) == 0


def test_decode_hx711_24bit_negative_twos_complement():
    bits = [1] + [0] * 23  # sign bit set, everything else zero -> most negative value
    assert decode_hx711_24bit(bits) == -0x800000


def test_decode_hx711_24bit_all_ones_is_negative_one():
    assert decode_hx711_24bit([1] * 24) == -1


def test_decode_hx711_24bit_wrong_length_raises():
    with pytest.raises(RuntimeError, match="expected 24 bits"):
        decode_hx711_24bit([0, 1, 1])


# ---- ENS160 — little-endian register decode, pure/testable ---------------------------


def test_decode_ens160_known_values():
    aqi, tvoc, eco2 = decode_ens160(bytes([3]), bytes([0x2C, 0x01]), bytes([0x90, 0x01]))
    assert aqi == 3
    assert tvoc == pytest.approx(300.0)  # 0x012C little-endian
    assert eco2 == pytest.approx(400.0)  # 0x0190 little-endian


def test_decode_ens160_wrong_aqi_length_raises():
    with pytest.raises(RuntimeError, match="expected 1 AQI byte"):
        decode_ens160(bytes([1, 2]), bytes([0, 0]), bytes([0, 0]))


def test_decode_ens160_wrong_data_length_raises():
    with pytest.raises(RuntimeError, match="expected 2 bytes each"):
        decode_ens160(bytes([1]), bytes([0]), bytes([0, 0]))


# ---- SCD4x — CRC8 (shared) and decode math, pure/testable ----------------------------


def test_decode_scd4x_known_values():
    co2_bytes = bytes([0x01, 0x90])  # 400 ppm
    temp_bytes = bytes([0x00, 0x00])  # raw 0 -> -45C
    hum_bytes = bytes([0xFF, 0xFF])  # raw max -> ~100% RH
    raw = (
        co2_bytes + bytes([_crc8(co2_bytes)])
        + temp_bytes + bytes([_crc8(temp_bytes)])
        + hum_bytes + bytes([_crc8(hum_bytes)])
    )
    co2_ppm, temp_c, rh_pct = decode_scd4x(raw)
    assert co2_ppm == 400.0
    assert temp_c == pytest.approx(-45.0)
    assert rh_pct == pytest.approx(100.0, abs=0.01)


def test_decode_scd4x_divides_by_65536_not_65535():
    # SCD4x's own documented formula divides by 2^16 exactly — at raw=32768 (half of
    # 65536) temp should land exactly on -45 + 175*0.5 = 42.5, not something skewed by
    # SHT31's off-by-one divisor.
    temp_bytes = bytes([0x80, 0x00])  # 32768
    zero = bytes([0x00, 0x00])
    raw = zero + bytes([_crc8(zero)]) + temp_bytes + bytes([_crc8(temp_bytes)]) + zero + bytes([_crc8(zero)])
    _, temp_c, _ = decode_scd4x(raw)
    assert temp_c == pytest.approx(42.5)


def test_decode_scd4x_bad_crc_raises():
    with pytest.raises(RuntimeError, match="CRC"):
        decode_scd4x(bytes(9))


def test_decode_scd4x_wrong_length_raises():
    with pytest.raises(RuntimeError, match="expected 9 bytes"):
        decode_scd4x(bytes([0x00, 0x00]))


# ---- BME280 — calibration/ADC byte parsing (fully controllable, no ambiguity) -------


def test_parse_bme280_calibration_unsigned_and_signed_fields():
    calib1 = bytearray(26)
    calib1[0:2] = (27504).to_bytes(2, "little")  # dig_T1, unsigned
    calib1[2:4] = (26435).to_bytes(2, "little", signed=True)  # dig_T2, signed positive
    calib1[4:6] = (-1000).to_bytes(2, "little", signed=True)  # dig_T3, signed negative
    calib2 = bytes([75])  # dig_H1
    calib3 = bytes(7)

    cal = parse_bme280_calibration(bytes(calib1), calib2, calib3)
    assert cal.dig_T1 == 27504
    assert cal.dig_T2 == 26435
    assert cal.dig_T3 == -1000
    assert cal.dig_H1 == 75


def test_parse_bme280_calibration_h4_h5_nibble_packing():
    # dig_H4 = (E4 << 4) | (E5 & 0x0F); dig_H5 = (E6 << 4) | (E5 >> 4) — the two
    # 12-bit values share byte E5, one nibble each. E4=0x01, E5=0x23, E6=0x04 ->
    # dig_H4 = (0x01 << 4) | 0x3 = 0x013 = 19; dig_H5 = (0x04 << 4) | 0x2 = 0x042 = 66.
    calib3 = bytes([0x00, 0x00, 0x00, 0x01, 0x23, 0x04, 0x00])
    cal = parse_bme280_calibration(bytes(26), bytes([0]), calib3)
    assert cal.dig_H4 == 19
    assert cal.dig_H5 == 66


def test_parse_bme280_calibration_wrong_lengths_raise():
    with pytest.raises(RuntimeError, match="expected 26 calibration bytes"):
        parse_bme280_calibration(bytes(10), bytes([0]), bytes(7))
    with pytest.raises(RuntimeError, match="expected 1 calibration byte"):
        parse_bme280_calibration(bytes(26), bytes(2), bytes(7))
    with pytest.raises(RuntimeError, match="expected 7 calibration bytes"):
        parse_bme280_calibration(bytes(26), bytes([0]), bytes(3))


def test_parse_bme280_raw_adc_20bit_and_16bit_layout():
    # press = 0xABCDE (20 bits): msb=0xAB, lsb=0xCD, xlsb top nibble=0xE0
    # temp = 0x12345 (20 bits): msb=0x12, lsb=0x34, xlsb top nibble=0x50
    # hum = 0x6789 (16 bits): msb=0x67, lsb=0x89
    data = bytes([0xAB, 0xCD, 0xE0, 0x12, 0x34, 0x50, 0x67, 0x89])
    adc_p, adc_t, adc_h = parse_bme280_raw_adc(data)
    assert adc_p == 0xABCDE
    assert adc_t == 0x12345
    assert adc_h == 0x6789


def test_parse_bme280_raw_adc_wrong_length_raises():
    with pytest.raises(RuntimeError, match="expected 8 data bytes"):
        parse_bme280_raw_adc(bytes(4))


# ---- BME280 — compensation math, tested for structural correctness rather than an
# exact worked-example match this implementation can't fully guarantee — see the
# "kind": "bme280" docstring's honesty note. ------------------------------------------


def _simple_calibration(**overrides) -> Bme280Calibration:
    values = dict(
        dig_T1=27504, dig_T2=26435, dig_T3=-1000,
        dig_P1=36477, dig_P2=-10685, dig_P3=3024, dig_P4=2855, dig_P5=140,
        dig_P6=-7, dig_P7=15500, dig_P8=-14600, dig_P9=6000,
        dig_H1=75, dig_H2=350, dig_H3=0, dig_H4=310, dig_H5=50, dig_H6=30,
    )
    values.update(overrides)
    return Bme280Calibration(**values)


def test_compensate_bme280_temperature_increases_with_higher_adc_reading():
    # dig_T3=0 isolates the var1 term, which is directly proportional to adc_t with a
    # positive dig_T2 — an unambiguous, verifiable-by-construction monotonic relationship,
    # not dependent on trusting the formula's exact absolute output.
    cal = _simple_calibration(dig_T3=0)
    temp_low, _, _ = compensate_bme280(adc_t=400000, adc_p=400000, adc_h=30000, cal=cal)
    temp_high, _, _ = compensate_bme280(adc_t=600000, adc_p=400000, adc_h=30000, cal=cal)
    assert temp_high > temp_low


def test_compensate_bme280_pressure_guards_against_division_by_zero():
    # The datasheet's own formula defines var1 == 0 as invalid and calls for skipping
    # the division rather than raising ZeroDivisionError — dig_P1=0 forces that path.
    cal = _simple_calibration(dig_P1=0, dig_P2=0, dig_P3=0)
    _, pressure_hpa, _ = compensate_bme280(adc_t=400000, adc_p=400000, adc_h=30000, cal=cal)
    assert pressure_hpa == 0.0


def test_compensate_bme280_humidity_is_clamped_to_0_100():
    cal = _simple_calibration(dig_H2=32767, dig_H1=1)  # pushed toward saturating high
    _, _, rh_pct = compensate_bme280(adc_t=400000, adc_p=400000, adc_h=65535, cal=cal)
    assert 0.0 <= rh_pct <= 100.0


def test_compensate_bme280_runs_without_crashing_on_realistic_inputs():
    # Not a claim of numeric correctness (see the honesty note above) — just proof
    # the formula executes end to end and returns three finite, plausible-range
    # numbers for inputs in a real sensor's normal operating range.
    cal = _simple_calibration()
    temp_c, pressure_hpa, rh_pct = compensate_bme280(adc_t=519888, adc_p=415148, adc_h=32768, cal=cal)
    assert -40 < temp_c < 85  # BME280's documented operating range
    assert 300 < pressure_hpa < 1100  # documented operating range
    assert 0 <= rh_pct <= 100


# ---- config validation ----------------------------------------------------------------


async def test_read_without_sensors_raises():
    adapter = GpioAdapter()
    with pytest.raises(RuntimeError, match="adapter_config.sensors"):
        await adapter.read(make_room())


async def test_read_with_unknown_kind_raises():
    adapter = GpioAdapter()
    with pytest.raises(RuntimeError, match="unknown sensor kind"):
        await adapter.read(make_room(sensors=[{"kind": "carrier-pigeon", "metric": "x"}]))


def test_plugin_metadata_is_set():
    assert GpioAdapter.plugin_name == "Direct GPIO/I2C/1-Wire sensors"
    assert "sensors" in GpioAdapter.config_schema


# ---- digital GPIO — real, fully testable via gpiozero's own mock pin factory --------
# The one hardware-adjacent path that's genuinely verifiable without real hardware:
# gpiozero ships an official mock backend for exactly this purpose.


@pytest.fixture(autouse=True)
def mock_gpio():
    Device.pin_factory = MockFactory()
    yield
    Device.pin_factory.reset()


def _driven_pin(adapter: GpioAdapter, pin_number: int, active_high: bool):
    # The adapter caches one DigitalInputDevice per pin (real reason: avoid tearing
    # down and re-requesting the GPIO line every 5s poll cycle) — constructing it is
    # what the mock backend actually keys pin state against, so the device must exist
    # before driving the pin, not after. Getting it via the adapter's own cache
    # (rather than a fresh Device.pin_factory.pin() reference) exercises the exact
    # same object the adapter's read() will use.
    device = adapter._get_gpio_device(pin_number, active_high)
    return device.pin


async def test_gpio_digital_reads_active_high_true():
    adapter = GpioAdapter()
    _driven_pin(adapter, 17, active_high=True).drive_high()
    room = make_room(sensors=[{"kind": "gpio_digital", "pin": 17, "metric": "leak_detected", "active_high": True}])
    values = await adapter.read(room)
    assert values == {"leak_detected": 1.0}


async def test_gpio_digital_reads_active_high_false():
    adapter = GpioAdapter()
    _driven_pin(adapter, 17, active_high=True).drive_low()
    room = make_room(sensors=[{"kind": "gpio_digital", "pin": 17, "metric": "leak_detected", "active_high": True}])
    values = await adapter.read(room)
    assert values == {"leak_detected": 0.0}


async def test_gpio_digital_active_low_inverts_the_reading():
    adapter = GpioAdapter()
    # electrically low, but active_low means this IS the active state
    _driven_pin(adapter, 17, active_high=False).drive_low()
    room = make_room(sensors=[{"kind": "gpio_digital", "pin": 17, "metric": "leak_detected", "active_high": False}])
    values = await adapter.read(room)
    assert values == {"leak_detected": 1.0}


async def test_gpio_digital_custom_true_false_values():
    adapter = GpioAdapter()
    _driven_pin(adapter, 17, active_high=True).drive_high()
    room = make_room(
        sensors=[
            {
                "kind": "gpio_digital", "pin": 17, "metric": "leak_detected",
                "active_high": True, "true_value": 99.0, "false_value": -1.0,
            }
        ]
    )
    values = await adapter.read(room)
    assert values == {"leak_detected": 99.0}


async def test_gpio_digital_reuses_the_same_device_across_reads():
    adapter = GpioAdapter()
    pin = _driven_pin(adapter, 17, active_high=True)
    room = make_room(sensors=[{"kind": "gpio_digital", "pin": 17, "metric": "leak_detected", "active_high": True}])

    pin.drive_low()
    assert await adapter.read(room) == {"leak_detected": 0.0}
    pin.drive_high()
    assert await adapter.read(room) == {"leak_detected": 1.0}
    assert len(adapter._gpio_devices) == 1
