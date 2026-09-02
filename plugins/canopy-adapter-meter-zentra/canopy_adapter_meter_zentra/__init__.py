import os
from typing import Any, ClassVar

import aiohttp
from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room

REQUEST_TIMEOUT_SECONDS = 10
API_BASE = "https://api.zentracloud.io/v5"

# Sourced directly from ZENTRA Cloud's own published v5 API docs (docs.zentracloud.com,
# "API Documentation" article, fetched live) and cross-checked via web search:
#   - base URL `https://api.zentracloud.io/v5`
#   - auth via an `X-API-Key` header (key generated per-user under ZENTRA Cloud's
#     Integrations settings)
#   - `GET /devices/{device_id}/data?direction=descending&units=metric` — confirmed
#     as a real endpoint ("Pull time-series measurements for a single device")
# NOT independently confirmed: the exact JSON response envelope/field names for a
# reading (ZENTRA's own overview doc explicitly defers that to a separate "Get
# Device Readings" reference article this project's fetch tooling could not reach).
# Rather than guess a shape and silently return wrong values, `_extract_latest`
# below walks the response defensively and raises a clear, actionable error naming
# what it actually found if the expected structure isn't there — a real customer
# hitting that error has enough to file a support ticket or adjust `field_path`,
# not a mystery KeyError.


class MeterZentraAdapter(SensorAdapter):
    """
    METER Group ZENTRA Cloud — TEROS soil-moisture/EC/temperature probes, ATMOS
    weather sensors, PHYTOS leaf-wetness sensors, read via a ZL6/EM60G logger's
    cloud account. See this module's own top-of-file comment for exactly what's
    confirmed vs. not about the response shape.

    room.adapter_config shape:
        {
          "device_id": "z6-00930",         # from the ZENTRA Cloud device list
          "fields": {
            "soil_pct": "Water Content",   # sensor label as it appears in your
            "temp_f": "Temperature"        # ZENTRA Cloud dashboard for this device
          }
        }
    """

    plugin_name = "METER Group ZENTRA Cloud"
    plugin_description = (
        "TEROS/ATMOS/PHYTOS soil, substrate, and weather sensors via a ZL6/EM60G "
        "logger's ZENTRA Cloud account."
    )
    category: ClassVar[str] = "cloud"
    config_schema: ClassVar[dict[str, str]] = {
        "device_id": "Device serial/id as shown in ZENTRA Cloud (e.g. 'z6-00930')",
        "fields": "{metric_key: sensor label as shown in your ZENTRA Cloud dashboard for this device}",
    }
    required_env_vars: ClassVar[dict[str, str]] = {
        "CANOPY_METER_API_KEY": "ZENTRA Cloud API token (Integrations tab in your account settings)",
    }

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def connect(self, room: Room) -> None:
        pass  # session created lazily and shared across every room, see _get_session

    async def disconnect(self, room: Room) -> None:
        pass  # shared session; never torn down per-room, same as every other adapter

    async def read(self, room: Room) -> dict[str, float]:
        api_key = os.environ.get("CANOPY_METER_API_KEY")
        if not api_key:
            raise RuntimeError("meter_zentra adapter requires CANOPY_METER_API_KEY to be set")
        device_id = room.adapter_config.get("device_id")
        if not device_id:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.device_id")
        fields: dict[str, str] = room.adapter_config.get("fields") or {}
        if not fields:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.fields configured")

        session = self._get_session()
        headers = {"X-API-Key": api_key}
        params = {"direction": "descending", "units": "metric"}
        async with session.get(f"{API_BASE}/devices/{device_id}/data", headers=headers, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"ZENTRA Cloud request for device '{device_id}' returned HTTP {resp.status}: {text[:300]}")
            body = await resp.json(content_type=None)

        return _extract_latest(body, fields, device_id)

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS))
        return self._session


def _iter_readings(body: Any):
    """ZENTRA's exact envelope isn't confirmed (see module docstring) — this walks
    the most plausible shapes (a top-level list, or a dict with a 'data'/'readings'/
    'results' list) so a real response has a real chance of parsing without this
    adapter needing an update the moment the true shape is confirmed."""
    if isinstance(body, list):
        yield from body
        return
    if isinstance(body, dict):
        for key in ("data", "readings", "results"):
            value = body.get(key)
            if isinstance(value, list):
                yield from value
                return


def _extract_latest(body: Any, fields: dict[str, str], device_id: str) -> dict[str, float]:
    """Split out from the HTTP call so response parsing is directly unit-testable.
    Each configured field's sensor label is matched against whatever label/name-like
    key each reading entry has (again, defensive — the exact key name isn't
    confirmed) and the first (most recent, given direction=descending) match wins."""
    entries = list(_iter_readings(body))
    if not entries:
        raise RuntimeError(
            f"ZENTRA Cloud response for device '{device_id}' had no recognizable reading "
            f"list — top-level keys were {sorted(body.keys()) if isinstance(body, dict) else type(body).__name__}. "
            "This adapter's response parsing is unverified against a real account; please "
            "report the actual response shape so it can be fixed."
        )

    values: dict[str, float] = {}
    for metric, label in fields.items():
        match = next((e for e in entries if _entry_label(e) == label), None)
        if match is None:
            raise RuntimeError(f"metric '{metric}': no reading found with sensor label '{label}' for device '{device_id}'")
        value = _entry_value(match)
        if value is None:
            raise RuntimeError(f"metric '{metric}': reading for sensor label '{label}' had no numeric value field")
        values[metric] = value
    return values


def _entry_label(entry: dict) -> str | None:
    for key in ("sensor_label", "label", "name", "port_name"):
        if key in entry:
            return entry[key]
    return None


def _entry_value(entry: dict) -> float | None:
    for key in ("value", "value_1", "reading"):
        if key in entry:
            try:
                return float(entry[key])
            except (TypeError, ValueError):
                return None
    return None
