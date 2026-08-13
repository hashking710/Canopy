# Build context is the repo root (see docker-compose.yml) — not this directory —
# because this image also needs the plugins/ directory, which lives outside
# edge-agent/. Paths below are relative to the repo root.

FROM python:3.12-slim

WORKDIR /app

COPY edge-agent/pyproject.toml ./
COPY edge-agent/canopy_agent ./canopy_agent
COPY edge-agent/alembic ./alembic
COPY edge-agent/alembic.ini ./

# These plugins ship in the image by default (cheap dependencies, and it makes the
# plugin mechanism demonstrable out of the box); each stays entirely inert unless a
# room's adapter_type is actually set to use it. canopy-adapter-trolmaster is a
# scaffold only — its read() raises NotImplementedError until real vendor API access
# exists to build it against (see that package's docstring). canopy-adapter-gpio and
# canopy-adapter-atlas-ezo install and register fine here (this base image is Linux,
# so smbus2's fcntl dependency is satisfied), but actually reading a real sensor still
# needs real I2C/1-Wire/GPIO hardware passed through to the container (e.g. `docker
# run --device=/dev/i2c-1`) — see each package's own docstring for what's genuinely
# verified vs. implemented-from-datasheet-but-untested-against-real-hardware.
# canopy-adapter-ble/canopy-adapter-aranet4 (bleak) similarly install and register
# fine without a Bluetooth adapter present — bleak's Linux backend only touches
# BlueZ over D-Bus when actually scanning/connecting, not at import time — but need
# a real BLE adapter passed through (and BlueZ running) to actually read anything.
COPY plugins/canopy-adapter-ac-infinity /plugins/canopy-adapter-ac-infinity
COPY plugins/canopy-adapter-ac-infinity-ble /plugins/canopy-adapter-ac-infinity-ble
COPY plugins/canopy-adapter-emporia-vue /plugins/canopy-adapter-emporia-vue
COPY plugins/canopy-adapter-modbus /plugins/canopy-adapter-modbus
COPY plugins/canopy-adapter-trolmaster /plugins/canopy-adapter-trolmaster
COPY plugins/canopy-adapter-mqtt /plugins/canopy-adapter-mqtt
COPY plugins/canopy-adapter-shelly /plugins/canopy-adapter-shelly
COPY plugins/canopy-adapter-ecowitt /plugins/canopy-adapter-ecowitt
COPY plugins/canopy-adapter-switchbot /plugins/canopy-adapter-switchbot
COPY plugins/canopy-adapter-govee /plugins/canopy-adapter-govee
COPY plugins/canopy-adapter-gpio /plugins/canopy-adapter-gpio
COPY plugins/canopy-adapter-atlas-ezo /plugins/canopy-adapter-atlas-ezo
COPY plugins/canopy-adapter-ble /plugins/canopy-adapter-ble
COPY plugins/canopy-adapter-aranet4 /plugins/canopy-adapter-aranet4
COPY plugins/canopy-adapter-tuya /plugins/canopy-adapter-tuya
COPY plugins/canopy-adapter-rachio /plugins/canopy-adapter-rachio
COPY plugins/canopy-adapter-rainmachine /plugins/canopy-adapter-rainmachine
# Compliance-sync plugin, not a sensor adapter — inert unless
# CANOPY_COMPLIANCE_SYNC=metrc and real METRC credentials are set. See its own
# docstring for exactly which operations are implemented against a confirmed
# request shape vs. left honestly unimplemented.
COPY plugins/canopy-compliancesync-metrc /plugins/canopy-compliancesync-metrc

RUN pip install --no-cache-dir . \
    /plugins/canopy-adapter-ac-infinity \
    /plugins/canopy-adapter-ac-infinity-ble \
    /plugins/canopy-adapter-emporia-vue \
    /plugins/canopy-adapter-modbus \
    /plugins/canopy-adapter-trolmaster \
    /plugins/canopy-adapter-mqtt \
    /plugins/canopy-adapter-shelly \
    /plugins/canopy-adapter-ecowitt \
    /plugins/canopy-adapter-switchbot \
    /plugins/canopy-adapter-govee \
    /plugins/canopy-adapter-gpio \
    /plugins/canopy-adapter-atlas-ezo \
    /plugins/canopy-adapter-ble \
    /plugins/canopy-adapter-aranet4 \
    /plugins/canopy-adapter-tuya \
    /plugins/canopy-adapter-rachio \
    /plugins/canopy-adapter-rainmachine \
    /plugins/canopy-compliancesync-metrc

EXPOSE 8000

CMD ["uvicorn", "canopy_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
