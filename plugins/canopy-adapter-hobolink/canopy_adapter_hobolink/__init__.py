import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, ClassVar

import aiohttp
from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room

REQUEST_TIMEOUT_SECONDS = 15
TOKEN_URL = "https://webservice.hobolink.com/ws/auth/token"
API_BASE = "https://webservice.hobolink.com/ws"
TOKEN_REFRESH_MARGIN_SECONDS = 60
# How far back to ask for readings when polling for "the current value" — HOBOlink's
# data endpoint is a time-range export, not a single-latest-value lookup, so this
# adapter asks for a short recent window and takes the most recent entry returned,
# same approach as the ZENTRA adapter's descending-sort-then-take-first.
LOOKBACK_MINUTES = 30

# Sourced from Onset's own HOBOlink Web Services V3 Developer's Guide (document
# 25113, onsetcomp.com) via web search — confirmed: OAuth2 client_credentials against
# a /token endpoint under webservice.hobolink.com, and a data-export endpoint shaped
# `GET /data/file/{format}/user/{userId}?loggers={loggerList}&start_date_time=...
# &end_date_time=...`. NOT independently confirmed: the exact response JSON field
# names for a single reading — same "real confirmed request, defensive response
# parsing with a clear diagnostic error" posture as the ZENTRA adapter, rather than
# guessing a shape and returning silently wrong values.


class HobolinkAdapter(SensorAdapter):
    """
    Onset HOBOlink Web Services V3 — HOBO data loggers (temperature, humidity, soil
    moisture, and other HOBO sensor types depending on the logger model) via a
    HOBOlink cloud account. See this module's own top-of-file comment for exactly
    what's confirmed vs. not about the response shape.

    room.adapter_config shape:
        {
          "user_id": "123456",              # your HOBOlink numeric user id
          "logger_sn": "20958060",          # logger serial number
          "fields": {
            "temp_f": "Temperature",        # sensor label as it appears in HOBOlink
            "rh_pct": "RH"
          }
        }
    """

    plugin_name = "Onset HOBOlink"
    plugin_description = "HOBO data loggers (temperature, humidity, soil moisture, and more) via a HOBOlink cloud account."
    category: ClassVar[str] = "cloud"
    config_schema: ClassVar[dict[str, str]] = {
        "user_id": "Your HOBOlink numeric user id",
        "logger_sn": "Logger serial number, from the HOBOlink device list",
        "fields": "{metric_key: sensor label as shown in HOBOlink for this logger}",
    }
    required_env_vars: ClassVar[dict[str, str]] = {
        "CANOPY_HOBOLINK_CLIENT_ID": "HOBOlink Web Services client id (Onset-issued)",
        "CANOPY_HOBOLINK_CLIENT_SECRET": "HOBOlink Web Services client secret (Onset-issued)",
    }

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    async def connect(self, room: Room) -> None:
        pass  # session created lazily and shared across every room, see _get_session

    async def disconnect(self, room: Room) -> None:
        pass  # shared session; never torn down per-room, same as every other adapter

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS))
        return self._session

    async def _get_token(self) -> str:
        if self._token is not None and time.monotonic() < self._token_expires_at:
            return self._token

        client_id = os.environ.get("CANOPY_HOBOLINK_CLIENT_ID")
        client_secret = os.environ.get("CANOPY_HOBOLINK_CLIENT_SECRET")
        if not (client_id and client_secret):
            raise RuntimeError("hobolink adapter requires CANOPY_HOBOLINK_CLIENT_ID and CANOPY_HOBOLINK_CLIENT_SECRET")

        session = self._get_session()
        async with session.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"HOBOlink token request returned HTTP {resp.status}: {text[:300]}")
            data = await resp.json(content_type=None)

        self._token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        self._token_expires_at = time.monotonic() + expires_in - TOKEN_REFRESH_MARGIN_SECONDS
        return self._token

    async def read(self, room: Room) -> dict[str, float]:
        user_id = room.adapter_config.get("user_id")
        logger_sn = room.adapter_config.get("logger_sn")
        fields: dict[str, str] = room.adapter_config.get("fields") or {}
        if not user_id:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.user_id")
        if not logger_sn:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.logger_sn")
        if not fields:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.fields configured")

        token = await self._get_token()
        now = datetime.now(timezone.utc)
        params = {
            "loggers": logger_sn,
            "start_date_time": (now - timedelta(minutes=LOOKBACK_MINUTES)).strftime("%Y-%m-%d %H:%M:%S"),
            "end_date_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        }
        session = self._get_session()
        headers = {"Authorization": f"Bearer {token}"}
        async with session.get(f"{API_BASE}/data/file/JSON/user/{user_id}", headers=headers, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"HOBOlink data request for logger '{logger_sn}' returned HTTP {resp.status}: {text[:300]}")
            body = await resp.json(content_type=None)

        return _extract_latest(body, fields, logger_sn)


def _iter_series(body: Any):
    """HOBOlink's exact envelope isn't independently confirmed — walks the most
    plausible shapes (see this module's top-of-file comment)."""
    if isinstance(body, dict):
        series = body.get("series") or body.get("data") or body.get("observation_list")
        if isinstance(series, list):
            yield from series


def _extract_latest(body: Any, fields: dict[str, str], logger_sn: str) -> dict[str, float]:
    """Split out from the HTTP call so response parsing is directly unit-testable."""
    series = list(_iter_series(body))
    if not series:
        raise RuntimeError(
            f"HOBOlink response for logger '{logger_sn}' had no recognizable data series — "
            f"top-level keys were {sorted(body.keys()) if isinstance(body, dict) else type(body).__name__}. "
            "This adapter's response parsing is unverified against a real account; please "
            "report the actual response shape so it can be fixed."
        )

    values: dict[str, float] = {}
    for metric, label in fields.items():
        matches = [s for s in series if _series_label(s) == label]
        if not matches:
            raise RuntimeError(f"metric '{metric}': no series found with sensor label '{label}' for logger '{logger_sn}'")
        readings = matches[0].get("readings") or matches[0].get("values") or []
        if not readings:
            raise RuntimeError(f"metric '{metric}': series for sensor label '{label}' had no readings in the lookback window")
        value = _reading_value(readings[-1])  # most recent, given an ascending time-ordered export
        if value is None:
            raise RuntimeError(f"metric '{metric}': latest reading for sensor label '{label}' had no numeric value field")
        values[metric] = value
    return values


def _series_label(series: dict) -> str | None:
    for key in ("sensor_measurement_type", "label", "name"):
        if key in series:
            return series[key]
    return None


def _reading_value(reading: Any) -> float | None:
    if isinstance(reading, dict):
        for key in ("value", "reading_value"):
            if key in reading:
                try:
                    return float(reading[key])
                except (TypeError, ValueError):
                    return None
        return None
    try:
        return float(reading)
    except (TypeError, ValueError):
        return None
