"""
RainMachine smart irrigation controller — like the Rachio adapter, this reports
whether a given zone is currently watering rather than a continuous climate value,
for correlating irrigation/fertigation runs against soil-moisture/EC/humidity
spikes from the other adapters in this ecosystem.

Unlike Rachio, RainMachine's API is genuinely local (HTTPS directly to the device on
your LAN, self-signed cert, no cloud round-trip) — real, documented via RainMachine's
published API and consistent with how the well-known Home Assistant integration for
it works: log in once with the device's local access password to get a short-lived
access token, then query zone state using that token.

Confidence note, same as Rachio: real protocol shape, but the exact zone "state"
value semantics (this adapter treats any non-zero state as "active") are implemented
from recollection, not verified against a real device — the login/token/request
plumbing itself is verified against a real local test server.
"""

from __future__ import annotations

import os
from typing import ClassVar

import aiohttp
from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room

REQUEST_TIMEOUT_SECONDS = 10


class RainMachineAdapter(SensorAdapter):
    """
    room.adapter_config shape:
        {"host": "https://192.168.1.60:8080", "zone_id": 1, "metric": "zone_active"}

    "host" includes the scheme and port (RainMachine's local API defaults to HTTPS on
    8080 with a self-signed cert — this adapter disables certificate verification for
    that reason, same trust model as accessing the device's own local web UI
    directly). CANOPY_RAINMACHINE_PASSWORD is the device's local access password
    (set in the RainMachine app), shared across every room using this adapter.
    """

    plugin_name = "RainMachine (local API)"
    plugin_description = "Reports whether a RainMachine zone is currently watering — local HTTPS API, no cloud account."
    category: ClassVar[str] = "local"
    config_schema: ClassVar[dict[str, str]] = {
        "host": "Device base URL, e.g. https://192.168.1.60:8080",
        "zone_id": "RainMachine zone UID to watch",
    }
    required_env_vars: ClassVar[dict[str, str]] = {
        "CANOPY_RAINMACHINE_PASSWORD": "The device's local access password (set in the RainMachine app)",
    }
    default_metric_config: ClassVar[dict[str, dict]] = {
        "zone_active": {"label": "zone active", "unit": "", "decimals": 0},
    }

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._tokens: dict[str, str] = {}  # host -> access_token, refreshed on auth failure
        # host -> the password its cached token was issued for — compared against
        # the freshly-read env var on every call so a credential changed through
        # the dashboard (routers/secrets.py) forces a real re-login instead of
        # silently continuing to use a token issued under the old password.
        self._token_password: dict[str, str] = {}

    async def connect(self, room: Room) -> None:
        pass  # session/token created lazily and shared across rooms, see read()

    async def disconnect(self, room: Room) -> None:
        pass  # shared session; never torn down per-room, same as every other adapter

    async def read(self, room: Room) -> dict[str, float]:
        # Read fresh on every call, not cached at __init__: this adapter instance is
        # long-lived and shared across every room using it (adapters/registry.py),
        # so a credential set through the dashboard must take effect on the very
        # next poll cycle, not only after a container restart.
        password = os.environ.get("CANOPY_RAINMACHINE_PASSWORD")
        if not password:
            raise RuntimeError("rainmachine adapter requires CANOPY_RAINMACHINE_PASSWORD to be set")
        host = room.adapter_config.get("host")
        zone_id = room.adapter_config.get("zone_id")
        if not host or zone_id is None:
            raise RuntimeError(f"room '{room.id}' needs both adapter_config.host and adapter_config.zone_id")

        session = self._get_session()
        if host not in self._tokens or self._token_password.get(host) != password:
            self._tokens[host] = await self._login(session, host, password)
            self._token_password[host] = password

        zones = await self._get_zones(session, host, self._tokens[host])
        return {"zone_active": 1.0 if is_zone_active(zones, zone_id) else 0.0}

    async def _login(self, session: aiohttp.ClientSession, host: str, password: str) -> str:
        async with session.post(
            f"{host}/api/4/auth/login", json={"pwd": password, "remember": True}, ssl=False
        ) as resp:
            body = await resp.json(content_type=None)
            if resp.status != 200 or "access_token" not in body:
                raise RuntimeError(f"RainMachine login to {host} failed: {body}")
            return body["access_token"]

    async def _get_zones(self, session: aiohttp.ClientSession, host: str, access_token: str) -> list[dict]:
        async with session.get(f"{host}/api/4/zone", params={"access_token": access_token}, ssl=False) as resp:
            if resp.status != 200:
                raise RuntimeError(f"RainMachine zone request to {host} returned HTTP {resp.status}")
            body = await resp.json(content_type=None)
            return body.get("zones", [])

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS))
        return self._session


def is_zone_active(zones: list[dict], zone_id) -> bool:
    """Split out from the HTTP calls so the zone-state check is directly
    unit-testable. Treats any non-zero "state" as active — RainMachine's exact state
    value enumeration (queued vs. actively watering, etc.) isn't distinguished here."""
    for zone in zones:
        if zone.get("uid") == zone_id:
            return bool(zone.get("state", 0))
    return False
