"""
Rachio smart irrigation controller — reports whether a given zone is currently
watering, not a continuous climate reading. Real value for a cultivation dashboard:
correlating irrigation/fertigation runs against soil-moisture, EC, or humidity
spikes from the other adapters in this ecosystem, rather than having to cross-
reference Rachio's own separate app by hand.

Confidence note: Rachio's public API (rachio.readme.io) is real and documented, but
it's fundamentally a scheduling/control API, not a sensor-reporting one — there's no
single canonical "is this zone watering right now" reading the way a temp sensor has
one obvious value. This adapter reads the device's current-schedule endpoint and
checks whether the configured zone appears in it; the exact response shape is
implemented from recollection of the documented API, not verified against a real
account. Treat this the same as the other cloud adapters in this ecosystem
(SwitchBot/Govee/Ecowitt): real protocol, unverified against a live account.
"""

from __future__ import annotations

import os
from typing import ClassVar

import aiohttp
from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room

API_BASE = "https://api.rach.io/1/public"
REQUEST_TIMEOUT_SECONDS = 10


class RachioAdapter(SensorAdapter):
    """
    room.adapter_config shape:
        {"device_id": "...", "zone_id": "...", "metric": "zone_active"}

    Reports 1.0 if the configured zone_id is the one currently running on that
    device, 0.0 otherwise. device_id/zone_id are both from Rachio's API (or the
    app's own share/API tooling) — CANOPY_RACHIO_API_KEY (Account Settings -> API
    Key in the Rachio app) is shared across every room using this adapter.
    """

    plugin_name = "Rachio (Cloud API)"
    plugin_description = "Reports whether a Rachio zone is currently watering — correlate irrigation runs with other sensor readings."
    category: ClassVar[str] = "cloud"
    config_schema: ClassVar[dict[str, str]] = {
        "device_id": "Rachio controller device id",
        "zone_id": "Rachio zone id to watch",
    }
    required_env_vars: ClassVar[dict[str, str]] = {
        "CANOPY_RACHIO_API_KEY": "API key from the Rachio app (Account Settings → API Key)",
    }
    default_metric_config: ClassVar[dict[str, dict]] = {
        "zone_active": {"label": "zone active", "unit": "", "decimals": 0},
    }

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def connect(self, room: Room) -> None:
        pass  # session created lazily and shared across every room, see _get_session

    async def disconnect(self, room: Room) -> None:
        pass  # shared session; never torn down per-room, same as every other adapter

    async def read(self, room: Room) -> dict[str, float]:
        # Read fresh on every call, not cached at __init__: this adapter instance is
        # long-lived and shared across every room using it (adapters/registry.py),
        # so a credential set through the dashboard's credentials screen
        # (routers/secrets.py) must take effect on the very next poll cycle, not
        # only after a container restart.
        api_key = os.environ.get("CANOPY_RACHIO_API_KEY")
        if not api_key:
            raise RuntimeError("rachio adapter requires CANOPY_RACHIO_API_KEY to be set")
        device_id = room.adapter_config.get("device_id")
        zone_id = room.adapter_config.get("zone_id")
        if not device_id or not zone_id:
            raise RuntimeError(f"room '{room.id}' needs both adapter_config.device_id and adapter_config.zone_id")

        session = self._get_session()
        headers = {"Authorization": f"Bearer {api_key}"}
        async with session.get(f"{API_BASE}/device/{device_id}/current_schedule", headers=headers) as resp:
            if resp.status == 204:
                body: dict = {}
            elif resp.status != 200:
                raise RuntimeError(f"Rachio current_schedule request for '{device_id}' failed: HTTP {resp.status}")
            else:
                body = await resp.json(content_type=None)

        return {"zone_active": 1.0 if is_zone_active(body, zone_id) else 0.0}

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS))
        return self._session


def is_zone_active(current_schedule: dict, zone_id: str) -> bool:
    """Split out from the HTTP call so the "is this our zone" check is directly
    unit-testable. An empty/absent response (device idle) means not active; a
    populated response with a matching zoneId means it is."""
    if not current_schedule:
        return False
    return current_schedule.get("zoneId") == zone_id
