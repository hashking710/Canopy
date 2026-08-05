import os
import uuid
from typing import Any, ClassVar

import aiohttp
from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room

API_BASE = "https://openapi.api.govee.com/router/api/v1"
REQUEST_TIMEOUT_SECONDS = 10


class GoveeAdapter(SensorAdapter):
    """
    Govee cloud API (Developer API v1) — H5xxx-series temperature+humidity sensors.
    A real, documented, versioned public API (openapi.api.govee.com), auth'd with a
    single API key issued in the Govee Home app (Profile -> Settings -> Apply for
    API Key) — no HMAC signing needed, unlike SwitchBot's. Not verified against a
    real account/device here; implemented straight from Govee's published API docs.

    room.adapter_config shape:
        {"sku": "H5179", "device": "AA:BB:CC:DD:EE:FF:11:22"}   # both from the app,
                                                                    or GET /user/devices
    """

    plugin_name = "Govee (Cloud API)"
    plugin_description = "Govee H5xxx-series temperature+humidity sensors, via Govee's official cloud API."
    category: ClassVar[str] = "cloud"
    config_schema: ClassVar[dict[str, str]] = {
        "sku": "Device model/SKU (e.g. 'H5179'), from the Govee Home app or GET /user/devices",
        "device": "Device MAC/id, from the Govee Home app or GET /user/devices",
    }
    required_env_vars: ClassVar[dict[str, str]] = {
        "CANOPY_GOVEE_API_KEY": "API key requested in the Govee Home app (Settings → Apply for API Key)",
    }
    default_metric_config: ClassVar[dict[str, dict]] = {
        "temp_f": {"label": "temp", "unit": "°F", "decimals": 1},
        "rh_pct": {"label": "RH", "unit": "%", "decimals": 1},
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
        api_key = os.environ.get("CANOPY_GOVEE_API_KEY")
        if not api_key:
            raise RuntimeError("govee adapter requires CANOPY_GOVEE_API_KEY to be set")
        sku = room.adapter_config.get("sku")
        device = room.adapter_config.get("device")
        if not sku or not device:
            raise RuntimeError(f"room '{room.id}' needs both adapter_config.sku and adapter_config.device")

        session = self._get_session()
        body = {"requestId": str(uuid.uuid4()), "payload": {"sku": sku, "device": device}}
        headers = {"Govee-API-Key": api_key, "Content-Type": "application/json"}
        async with session.post(f"{API_BASE}/device/state", json=body, headers=headers) as resp:
            response_body = await resp.json(content_type=None)
            if resp.status != 200 or response_body.get("code") != 200:
                raise RuntimeError(f"Govee device/state request for '{device}' failed: {response_body}")

        return _parse_capabilities(response_body.get("payload", {}).get("capabilities", []))

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS))
        return self._session


def _parse_capabilities(capabilities: list[dict[str, Any]]) -> dict[str, float]:
    """Split out from the HTTP call so response parsing is directly unit-testable.
    Govee's state response reports every capability the device has (power, sensors,
    online status, ...) as a flat list keyed by `instance` — this picks out just the
    two this adapter knows how to map, same "report what's actually there, don't
    assume a fixed shape" approach as SwitchBot's/Shelly's."""
    values: dict[str, float] = {}
    for cap in capabilities:
        instance = cap.get("instance")
        value = (cap.get("state") or {}).get("value")
        if value is None:
            continue
        if instance == "sensorTemperature":
            values["temp_f"] = float(value) * 9 / 5 + 32  # Govee reports Celsius regardless of app display unit
        elif instance == "sensorHumidity":
            values["rh_pct"] = float(value)
    return values
