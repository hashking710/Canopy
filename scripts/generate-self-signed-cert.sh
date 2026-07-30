#!/usr/bin/env bash
# Generates a self-signed TLS cert/key pair for LAN-only Canopy deployments — a Pi
# serving its dashboard to devices on the same network, with no public domain and no
# need for a real CA. Not for anything internet-facing; use a reverse proxy with a real
# certificate (Caddy + Let's Encrypt is the easy path — see docs/deployment-tls.md) once
# this needs to be reachable from outside your LAN.
#
# Usage: ./generate-self-signed-cert.sh [output-dir] [hostname-or-ip]
set -euo pipefail

# Git Bash on Windows rewrites leading-slash arguments (like openssl's -subj "/CN=...")
# into Windows paths before they reach openssl. Harmless no-op on real Linux/macOS.
export MSYS_NO_PATHCONV=1

OUT_DIR="${1:-./certs}"
HOST="${2:-canopy.local}"
DAYS=825  # matches modern browsers' max cert lifetime for self-signed/private CAs

mkdir -p "$OUT_DIR"

openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "$OUT_DIR/key.pem" \
  -out "$OUT_DIR/cert.pem" \
  -days "$DAYS" \
  -subj "/CN=$HOST" \
  -addext "subjectAltName=DNS:$HOST,DNS:localhost,IP:127.0.0.1"

chmod 600 "$OUT_DIR/key.pem"

echo "Wrote $OUT_DIR/cert.pem and $OUT_DIR/key.pem (valid $DAYS days, CN=$HOST)"
echo
echo "Run edge-agent with TLS directly:"
echo "  uvicorn canopy_agent.main:app --host 0.0.0.0 --port 8443 --ssl-keyfile $OUT_DIR/key.pem --ssl-certfile $OUT_DIR/cert.pem"
echo
echo "Browsers will warn about this cert being self-signed/untrusted — that's expected"
echo "for LAN use. See docs/deployment-tls.md for the reverse-proxy alternative that"
echo "avoids the warning."
