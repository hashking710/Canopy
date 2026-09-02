# Build context is the repo root (see docker-compose.yml) — not this directory —
# because this image also needs the plugins/ directory, which lives outside
# edge-agent/. Paths below are relative to the repo root.

FROM python:3.12-slim

# Baked in at build time (see docker-compose.yml's build.args and deploy/install.sh,
# which export this from `git rev-parse HEAD` before building) so the running
# container can report its own version — see routers/version.py. Defaults to
# "unknown" for a manual `docker build`/local dev image with no git context passed
# through; the version UI treats that as "can't check for updates" rather than
# guessing.
ARG CANOPY_GIT_SHA=unknown
ENV CANOPY_GIT_SHA=$CANOPY_GIT_SHA

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
# Six more cloud/LAN adapters — same "ships by default, entirely inert unless a
# room actually uses it" posture as everything above. meter-zentra and hobolink are
# real, confirmed-against-published-docs implementations. priva has a real,
# confirmed OAuth2 token flow but an unimplemented telemetry read (needs a real
# account to confirm the request shape). growlink, argus, and pulsegrow are
# scaffolds only, same as canopy-adapter-trolmaster — real vendor infrastructure
# confirmed to exist, but read() raises NotImplementedError until real account
# access exists to confirm the exact protocol against. See each package's own
# docstring.
COPY plugins/canopy-adapter-meter-zentra /plugins/canopy-adapter-meter-zentra
COPY plugins/canopy-adapter-hobolink /plugins/canopy-adapter-hobolink
COPY plugins/canopy-adapter-priva /plugins/canopy-adapter-priva
COPY plugins/canopy-adapter-growlink /plugins/canopy-adapter-growlink
COPY plugins/canopy-adapter-argus /plugins/canopy-adapter-argus
COPY plugins/canopy-adapter-pulsegrow /plugins/canopy-adapter-pulsegrow
# Compliance-sync plugin, not a sensor adapter — inert unless
# CANOPY_COMPLIANCE_SYNC=metrc and real METRC credentials are set. See its own
# docstring for exactly which operations are implemented against a confirmed
# request shape vs. left honestly unimplemented.
COPY plugins/canopy-compliancesync-metrc /plugins/canopy-compliancesync-metrc
# Menu-sync plugins — inert unless CANOPY_MENU_SYNC is set to one of them. The mock
# one has zero external dependency and is a real, usable "generic POS" out of the
# box; the Weedmaps one needs CANOPY_WEEDMAPS_CLIENT_ID/_CLIENT_SECRET/_MENU_ID and,
# per its own docstring, real Weedmaps integration-partner approval (their
# onboarding is currently paused) before it can actually go live.
COPY plugins/canopy-menusync-mock /plugins/canopy-menusync-mock
COPY plugins/canopy-menusync-weedmaps /plugins/canopy-menusync-weedmaps

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
    /plugins/canopy-adapter-meter-zentra \
    /plugins/canopy-adapter-hobolink \
    /plugins/canopy-adapter-priva \
    /plugins/canopy-adapter-growlink \
    /plugins/canopy-adapter-argus \
    /plugins/canopy-adapter-pulsegrow \
    /plugins/canopy-compliancesync-metrc \
    /plugins/canopy-menusync-mock \
    /plugins/canopy-menusync-weedmaps

EXPOSE 8000

CMD ["uvicorn", "canopy_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
