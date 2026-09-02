#!/usr/bin/env bash
# One-command installer for a single Raspberry Pi (or any Debian/Ubuntu host):
# installs Docker if missing, fetches Canopy, and brings the dashboard up via
# `docker compose`. Safe to re-run. See docs/os-image.md for the full guide.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/deploy/install.sh | bash
#   ./install.sh --multi-site          # also bring up mosquitto + master
#   ./install.sh --upgrade             # pull the latest release into an existing install
#
# Env overrides:
#   CANOPY_REPO=<owner>/<repo>   which GitHub repo to install from
#   CANOPY_VERSION=vX.Y.Z        pin a specific release tag instead of "latest"
#   CANOPY_INSTALL_DIR=/opt/canopy   where the source lands

set -euo pipefail

# Placeholder until this repo has a real GitHub remote — update this (or pass
# CANOPY_REPO) once it's pushed.
REPO="${CANOPY_REPO:-hashking710/Canopy}"
INSTALL_DIR="${CANOPY_INSTALL_DIR:-/opt/canopy}"
VERSION="${CANOPY_VERSION:-latest}"
COMPOSE_PROFILE_ARGS=()
UPGRADE=0

for arg in "$@"; do
  case "$arg" in
    --multi-site) COMPOSE_PROFILE_ARGS=(--profile multi-site) ;;
    --upgrade) UPGRADE=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

log() { echo "==> $*"; }

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This installer targets Linux (Raspberry Pi OS / Debian / Ubuntu)." >&2
  exit 1
fi

SUDO=""
if [[ "$(id -u)" != "0" ]]; then
  if command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
  else
    echo "Need root or sudo to install Docker and write to $INSTALL_DIR." >&2
    exit 1
  fi
fi

# --- Docker -------------------------------------------------------------

if ! command -v docker >/dev/null 2>&1; then
  log "Docker not found — installing via get.docker.com"
  curl -fsSL https://get.docker.com | $SUDO sh
  if [[ -n "$SUDO" ]]; then
    $SUDO usermod -aG docker "$(id -un)"
    log "Added $(id -un) to the docker group — log out and back in for this to"
    log "take effect outside this script (this script keeps using sudo for now)."
  fi
else
  log "Docker already installed ($(docker --version))"
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose (the plugin, not docker-compose v1) is required but missing" >&2
  echo "even after installing Docker — check get.docker.com's output above." >&2
  exit 1
fi

DOCKER="docker"
if [[ -n "$SUDO" ]] && ! docker info >/dev/null 2>&1; then
  # Group membership from a fresh install above hasn't taken effect in this
  # shell yet — fall back to sudo for the rest of this run only.
  DOCKER="$SUDO docker"
fi

# --- Fetch source ---------------------------------------------------------

if [[ -d "$INSTALL_DIR/.git" ]]; then
  log "Existing git checkout found at $INSTALL_DIR"
  if [[ "$UPGRADE" == "1" ]]; then
    log "Pulling latest changes"
    $SUDO git -C "$INSTALL_DIR" pull --ff-only
  fi
elif [[ -d "$INSTALL_DIR" && -n "$(ls -A "$INSTALL_DIR" 2>/dev/null || true)" ]]; then
  log "Found an existing non-git install at $INSTALL_DIR — leaving source as-is."
  log "Re-run with --upgrade only works for git checkouts; for a tarball install,"
  log "download the newer release tarball over this directory yourself."
else
  $SUDO mkdir -p "$INSTALL_DIR"
  $SUDO chown "$(id -un)":"$(id -gn)" "$INSTALL_DIR"

  DOWNLOAD_URL=""
  if [[ "$VERSION" == "latest" ]]; then
    log "Looking up the latest release of $REPO"
    DOWNLOAD_URL=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" \
      | grep -o '"browser_download_url": *"[^"]*\.tar\.gz"' \
      | head -1 | cut -d'"' -f4 || true)
  else
    DOWNLOAD_URL="https://github.com/$REPO/releases/download/$VERSION/canopy-$VERSION.tar.gz"
  fi

  if [[ -n "$DOWNLOAD_URL" ]] && curl -fsSL -o /tmp/canopy-release.tar.gz "$DOWNLOAD_URL" 2>/dev/null; then
    log "Downloaded release tarball, extracting to $INSTALL_DIR"
    tar -xzf /tmp/canopy-release.tar.gz -C "$INSTALL_DIR" --strip-components=1
    rm -f /tmp/canopy-release.tar.gz
  else
    log "No release tarball available yet — cloning the default branch instead"
    if ! command -v git >/dev/null 2>&1; then
      $SUDO apt-get update -qq && $SUDO apt-get install -y -qq git
    fi
    git clone --depth 1 "https://github.com/$REPO.git" "$INSTALL_DIR"
  fi
fi

# --- Bring the stack up ----------------------------------------------------

cd "$INSTALL_DIR"
# Bakes the running commit into the image so the dashboard's "check for updates"
# button (Settings -> Updates) has something real to compare against — see
# edge-agent/Dockerfile's CANOPY_GIT_SHA arg and routers/version.py. Empty (not
# "unknown") for a tarball install with no .git directory; the dashboard already
# treats an empty/unknown current version as "can't check," not a false negative.
export CANOPY_GIT_SHA="$([[ -d .git ]] && git rev-parse HEAD 2>/dev/null || true)"
log "Starting Canopy (docker compose up -d --build ${COMPOSE_PROFILE_ARGS[*]-})"
$DOCKER compose up -d --build "${COMPOSE_PROFILE_ARGS[@]}"

log "Waiting for the edge agent to come up"
for _ in $(seq 1 60); do
  if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
  echo "edge-agent didn't become healthy in time — check 'docker compose logs' in $INSTALL_DIR" >&2
  exit 1
fi

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
HOSTNAME_LOCAL="$(hostname).local"

echo
log "Canopy is running."
echo "    Dashboard:  http://${HOSTNAME_LOCAL}:5173  (or http://${IP:-<pi-ip>}:5173)"
echo "    API:        http://${HOSTNAME_LOCAL}:8000"
if [[ ${#COMPOSE_PROFILE_ARGS[@]} -gt 0 ]]; then
  echo "    Master API: http://${HOSTNAME_LOCAL}:9100"
fi
echo
echo "Installed at $INSTALL_DIR. Re-run this script with --upgrade to update a"
echo "git-based install, or --multi-site to add the mosquitto + master services."
