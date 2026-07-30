from typing import Any, ClassVar

import aiohttp
from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room

REQUEST_TIMEOUT_SECONDS = 8


class ShellyAdapter(SensorAdapter):
    """
    Shelly smart plug/relay power monitoring — purely local, no cloud account, no API
    key. Shelly's own local HTTP API is genuinely public and documented
    (shelly-api-docs.shelly.cloud), unlike AC Infinity's reverse-engineered one, so
    this talks to the real, stable protocol rather than something inferred from a
    third-party integration.

    Supports both API generations, since a lot of cheaper/older Shelly hardware is
    still Gen1:
      - Gen1 (Plug S, PM Mini, 1PM, etc.): GET /status
      - Gen2/Gen3 (Plus/Pro series): GET /rpc/Switch.GetStatus?id=<n>

    room.adapter_config shape:
        {
          "host": "192.168.1.30",
          "generation": 1 | 2,     # default 2 — check the device's own model/API docs
          "switch_id": 0,          # Gen2/3 only: which switch/output, default 0
          "username": "...",       # optional — only if local HTTP auth is enabled
          "password": "..."
        }

    Reports whatever the device itself actually has: power_w always, plus
    voltage_v/current_a/energy_wh/temp_c wherever that generation's status response
    includes them (Gen1 devices report a smaller set than Gen2/3).
    """

    plugin_name = "Shelly (local API)"
    plugin_description = (
        "Shelly smart plug/relay power monitoring over its local HTTP API — Gen1 and "
        "Gen2/3, no cloud account needed."
    )
    config_schema: ClassVar[dict[str, str]] = {
        "host": "Device IP/hostname on your LAN",
        "generation": "1 or 2 (Gen2 covers Gen3 too — same RPC API), default 2",
        "switch_id": "Gen2/3 only: which switch/output index, default 0",
        "username": "Optional — only if the device's local HTTP auth is enabled",
        "password": "Optional — only if the device's local HTTP auth is enabled",
    }

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def connect(self, room: Room) -> None:
        pass  # session is created lazily and shared across every room, see _get_session

    async def disconnect(self, room: Room) -> None:
        pass  # shared session; never torn down per-room, same as every other adapter

    async def read(self, room: Room) -> dict[str, float]:
        config = room.adapter_config
        host = config.get("host")
        if not host:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.host")
        generation = int(config.get("generation", 2))

        session = self._get_session()
        auth = None
        if config.get("username") and config.get("password"):
            auth = aiohttp.BasicAuth(config["username"], config["password"])

        if generation == 1:
            body = await self._get_json(session, f"http://{host}/status", auth)
            return _parse_gen1_status(body)
        if generation == 2:
            switch_id = int(config.get("switch_id", 0))
            body = await self._get_json(session, f"http://{host}/rpc/Switch.GetStatus?id={switch_id}", auth)
            return _parse_gen2_status(body)
        raise RuntimeError(f"room '{room.id}': unknown adapter_config.generation '{generation}' (must be 1 or 2)")

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS))
        return self._session

    async def _get_json(self, session: aiohttp.ClientSession, url: str, auth) -> dict:
        async with session.get(url, auth=auth) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Shelly request to {url} returned HTTP {resp.status}")
            return await resp.json(content_type=None)


def _parse_gen1_status(body: dict[str, Any]) -> dict[str, float]:
    """Split out from the HTTP call so the response-parsing logic is directly
    unit-testable against real documented response shapes without a network call."""
    values: dict[str, float] = {}
    meters = body.get("meters") or []
    if meters and "power" in meters[0]:
        values["power_w"] = float(meters[0]["power"])
    if "temperature" in body:
        values["temp_c"] = float(body["temperature"])
    return values


def _parse_gen2_status(body: dict[str, Any]) -> dict[str, float]:
    values: dict[str, float] = {}
    if "apower" in body:
        values["power_w"] = float(body["apower"])
    if "voltage" in body:
        values["voltage_v"] = float(body["voltage"])
    if "current" in body:
        values["current_a"] = float(body["current"])
    aenergy = body.get("aenergy") or {}
    if "total" in aenergy:
        values["energy_wh"] = float(aenergy["total"])
    temperature = body.get("temperature") or {}
    if "tC" in temperature:
        values["temp_c"] = float(temperature["tC"])
    return values
