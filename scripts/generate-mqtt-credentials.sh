#!/usr/bin/env bash
# Generates a mosquitto password file for Canopy's MQTT mesh, using the same
# eclipse-mosquitto Docker image already pulled for the mosquitto service itself —
# rather than requiring mosquitto_passwd to be installed locally, which most
# Canopy deployments (a Pi running everything through docker compose) won't have.
# See docs/mqtt-security.md for how this fits into the full secure-MQTT setup.
#
# Usage: ./generate-mqtt-credentials.sh <username> [password] [output-dir]
# If password is omitted, mosquitto_passwd is run interactively (it will prompt).
set -euo pipefail

USERNAME="${1:?usage: generate-mqtt-credentials.sh <username> [password] [output-dir]}"
PASSWORD="${2:-}"
OUT_DIR="${3:-./deploy}"

mkdir -p "$OUT_DIR"
PASSWD_FILE="$OUT_DIR/passwd"

# -c only on first creation — appending a second user to an existing file must not
# pass -c again, or it silently wipes out everyone already in it.
CREATE_FLAG="-c"
if [ -f "$PASSWD_FILE" ]; then
  CREATE_FLAG=""
  echo "Adding '$USERNAME' to existing $PASSWD_FILE"
fi

if [ -n "$PASSWORD" ]; then
  docker run --rm -v "$(pwd)/$OUT_DIR:/mosquitto/config" eclipse-mosquitto:2 \
    mosquitto_passwd -b $CREATE_FLAG /mosquitto/config/passwd "$USERNAME" "$PASSWORD"
else
  docker run --rm -it -v "$(pwd)/$OUT_DIR:/mosquitto/config" eclipse-mosquitto:2 \
    mosquitto_passwd $CREATE_FLAG /mosquitto/config/passwd "$USERNAME"
fi

echo "Wrote credentials for '$USERNAME' to $PASSWD_FILE"
echo
echo "Set these on every service that connects to the broker (edge-agent, master):"
echo "  CANOPY_MQTT_USERNAME=$USERNAME"
echo "  CANOPY_MQTT_PASSWORD=<the password you just set>"
echo
echo "Then point mosquitto at deploy/mosquitto.secure.conf.example (see"
echo "docs/mqtt-security.md) instead of the default anonymous mosquitto.conf."
