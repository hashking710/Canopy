import asyncio
from typing import Any, ClassVar

import aiohttp
from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room
from zeroconf import IPVersion, ServiceStateChange
from zeroconf.asyncio import AsyncServiceBrowser, AsyncZeroconf

REQUEST_TIMEOUT_SECONDS = 8

# Documented in Shelly's own API docs (shelly-api-docs.shelly.cloud, "mDNS Discovery")
# for Gen2/Gen3's RPC-based devices. Confidence note, same honesty pattern as the BLE
# adapters' protocol docs: Gen1 mDNS advertising is inconsistent across firmware
# versions and not relied on here, so discover() is only confirmed to find Gen2/Gen3
# hardware — Gen1 users may still need to type in an IP by hand.
MDNS_SERVICE_TYPE = "_shelly._tcp.local."
SCAN_TIMEOUT_SECONDS = 5.0


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
    category: ClassVar[str] = "local"
    config_schema: ClassVar[dict[str, str]] = {
        "host": "Device IP/hostname on your LAN",
        "generation": "1 or 2 (Gen2 covers Gen3 too — same RPC API), default 2",
        "switch_id": "Gen2/3 only: which switch/output index, default 0",
        "username": "Optional — only if the device's local HTTP auth is enabled",
        "password": "Optional — only if the device's local HTTP auth is enabled",
    }
    # Only actually finds anything when the edge-agent container can see real LAN
    # multicast traffic — the default Docker bridge network can't (see
    # docs/architecture.md's "Opt-in local-network discovery for Pi deployments"),
    # so this requires docker-compose.pi.yml's network_mode: host. Still declared
    # unconditionally true: supports_discovery describes what the adapter can do,
    # not what today's specific deployment happens to allow — same as how
    # required_env_vars doesn't change based on whether the var is already set.
    supports_discovery: ClassVar[bool] = True
    # Just power_w, not voltage/current/energy/temp — those are Gen2/3-only and
    # conditional even then (see _parse_gen2_status), so a fixed default risks rows
    # that never populate on Gen1 hardware; power_w is the one metric every
    # generation actually reports. Add rows for the rest if you're on Gen2/3.
    default_metric_config: ClassVar[dict[str, dict]] = {
        "power_w": {"label": "power", "unit": "W", "decimals": 1},
    }

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def connect(self, room: Room) -> None:
        pass  # session is created lazily and shared across every room, see _get_session

    async def disconnect(self, room: Room) -> None:
        pass  # shared session; never torn down per-room, same as every other adapter

    @classmethod
    async def discover(cls) -> list[dict]:
        raw = await _scan_mdns_service(MDNS_SERVICE_TYPE, SCAN_TIMEOUT_SECONDS)
        return _format_mdns_results(raw)

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


async def _scan_mdns_service(service_type: str, timeout: float) -> dict[str, list[str]]:
    """The live-network half of discover() — kept separate from the pure formatting
    step below so tests can monkeypatch this one function directly and verify the
    formatting logic without a real zeroconf/multicast environment (same split as
    canopy-adapter-ble's scan_for_nearby_devices/decode_ble_value boundary). Returns
    {mdns instance name: [ip addresses]} for every service seen advertising
    `service_type` within `timeout` seconds."""
    aiozc = AsyncZeroconf()
    found_names: set[str] = set()

    def on_change(zeroconf, service_type, name, state_change) -> None:
        if state_change is ServiceStateChange.Added:
            found_names.add(name)

    browser = AsyncServiceBrowser(aiozc.zeroconf, service_type, handlers=[on_change])
    try:
        await asyncio.sleep(timeout)
    finally:
        await browser.async_cancel()

    results: dict[str, list[str]] = {}
    try:
        for name in found_names:
            info = await aiozc.async_get_service_info(service_type, name)
            if info is not None:
                results[name] = info.parsed_addresses(IPVersion.V4Only)
    finally:
        await aiozc.async_close()
    return results


def _format_mdns_results(raw: dict[str, list[str]]) -> list[dict]:
    """Pure — fully unit-testable without any real mDNS traffic. Drops services that
    resolved a name but no address (can happen if a device disappears mid-scan);
    takes the first IPv4 address for a service advertising more than one, since
    adapter_config.host is a single string."""
    results = []
    for name, addresses in sorted(raw.items()):
        if not addresses:
            continue
        # mDNS instance names are "<instance>.<service_type>" — strip the service
        # type suffix so the UI shows e.g. "shellyplus1-a4cf12abcdef", not the full
        # "shellyplus1-a4cf12abcdef._shelly._tcp.local.".
        display_name = name.split(".")[0]
        results.append({"address": addresses[0], "name": display_name})
    return results


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
