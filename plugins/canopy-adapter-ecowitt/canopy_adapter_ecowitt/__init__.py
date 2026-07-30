from typing import Any, ClassVar

import aiohttp
from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room

REQUEST_TIMEOUT_SECONDS = 8
LIVEDATA_PATH = "/get_livedata_info"


class EcowittAdapter(SensorAdapter):
    """
    Ecowitt gateway (GW1000/GW2000/GW3000 and similar WiFi weather-station consoles)
    local API — no Ecowitt cloud account needed, reads straight off the gateway on
    your own LAN. The response shape below (a flat `id`/`val`/`unit` list per sensor,
    grouped by category — `common_list` for the main console sensors,
    `soil_ch<N>` for soil moisture channels, etc.) is sourced from Ecowitt's published
    "LAN Console API" documentation, not reverse-engineered — but hasn't been tested
    against a real gateway here. Verify the exact `id` codes your specific gateway
    firmware reports (they've been known to drift slightly across firmware versions)
    before relying on this.

    Rather than assuming a fixed metric set (a weather station reports very
    different things depending on which sensors are actually paired — outdoor
    temp/humidity, soil moisture channels, PM2.5, lightning, etc.), each room
    describes which of the gateway's own `id` codes it wants, same approach as the
    Modbus adapter's register map for the same reason: this device's actual shape is
    config-defined, not something one fixed schema could represent honestly.

    room.adapter_config shape:
        {
          "host": "192.168.1.40",
          "fields": {
            "temp_f": "0x02",      # outdoor temperature
            "rh_pct": "0x07",      # outdoor humidity
            "soil_pct": "0x0D"     # soil moisture channel 1, if paired
          }
        }
    """

    plugin_name = "Ecowitt (local LAN API)"
    plugin_description = (
        "Ecowitt weather station / soil sensor gateway (GW1000/GW2000/GW3000 and "
        "similar) over its local LAN API — no cloud account needed."
    )
    config_schema: ClassVar[dict[str, str]] = {
        "host": "Gateway IP/hostname on your LAN",
        "fields": "{metric_key: ecowitt_id_code} — see Ecowitt's LAN Console API docs for id codes",
    }

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def connect(self, room: Room) -> None:
        pass  # session created lazily and shared across every room, see _get_session

    async def disconnect(self, room: Room) -> None:
        pass  # shared session; never torn down per-room, same as every other adapter

    async def read(self, room: Room) -> dict[str, float]:
        config = room.adapter_config
        host = config.get("host")
        if not host:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.host")
        fields: dict[str, str] = config.get("fields") or {}
        if not fields:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.fields configured")

        session = self._get_session()
        async with session.get(f"http://{host}{LIVEDATA_PATH}") as resp:
            if resp.status != 200:
                raise RuntimeError(f"Ecowitt request to {host} returned HTTP {resp.status}")
            body = await resp.json(content_type=None)

        readings_by_id = _flatten_readings(body)
        values: dict[str, float] = {}
        for metric, ecowitt_id in fields.items():
            entry = readings_by_id.get(ecowitt_id)
            if entry is None:
                raise RuntimeError(f"metric '{metric}': gateway response has no sensor with id '{ecowitt_id}'")
            values[metric] = entry
        return values

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS))
        return self._session


def _flatten_readings(body: dict[str, Any]) -> dict[str, float]:
    """Split out from the HTTP call so response parsing is directly unit-testable.
    The gateway groups sensors into several named lists (common_list, soil_chN, ...)
    — this flattens all of them into one {id: value} lookup regardless of which list
    a given sensor happened to be reported under, since adapter_config only cares
    about the id, not which category it's filed in."""
    flattened: dict[str, float] = {}
    for key, value in body.items():
        if not isinstance(value, list):
            continue
        for entry in value:
            if not isinstance(entry, dict) or "id" not in entry or "val" not in entry:
                continue
            try:
                flattened[entry["id"]] = float(entry["val"])
            except (TypeError, ValueError):
                continue  # non-numeric fields (e.g. a battery level reported as "Normal") are skipped
    return flattened
