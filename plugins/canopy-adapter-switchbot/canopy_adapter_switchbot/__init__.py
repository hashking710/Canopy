import base64
import hashlib
import hmac
import os
import time
import uuid
from typing import Any, ClassVar

import aiohttp
from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room

API_BASE = "https://api.switch-bot.com/v1.1"
REQUEST_TIMEOUT_SECONDS = 10

# SwitchBot's is a genuinely public, official, documented API
# (github.com/OpenWonderLabs/SwitchBotAPI) — unlike AC Infinity's reverse-engineered
# one, this is implemented straight from that documentation. Still not verified
# against a real account/device here; a real API response is the strongest
# confirmation this is exactly right.
CELSIUS_DEVICE_TYPES_NOTE = "temperature is always reported in Celsius regardless of the app's display unit setting"


class SwitchBotAdapter(SensorAdapter):
    """
    SwitchBot cloud API — Meter/MeterPlus/Hub2/Outdoor Meter temperature+humidity
    sensors. Cheap, widely available consumer hardware with a real, documented,
    versioned public API (v1.1) — no reverse engineering involved, unlike AC
    Infinity's.

    Auth is HMAC-SHA256 request signing (see _sign_headers), using a token + secret
    pair generated in the SwitchBot app (Profile -> Preferences -> Developer Options).
    Shared across every room on this adapter, same as AC Infinity's account
    credentials — set once via env vars, not per-room.

    room.adapter_config shape:
        {"device_id": "ABCDEF123456"}   # SwitchBot's own device id, from the app or
                                          # GET /v1.1/devices
    """

    plugin_name = "SwitchBot (Cloud API)"
    plugin_description = (
        "SwitchBot Meter/MeterPlus/Hub2 temperature+humidity sensors, via "
        "SwitchBot's official cloud API."
    )
    config_schema: ClassVar[dict[str, str]] = {"device_id": "SwitchBot device ID, from the app or GET /v1.1/devices"}
    required_env_vars: ClassVar[dict[str, str]] = {
        "CANOPY_SWITCHBOT_TOKEN": "Open token, from the SwitchBot app (Profile → Preferences → App Version → tap 10x → Open Token)",
        "CANOPY_SWITCHBOT_SECRET": "Secret key, shown alongside the open token",
    }

    def __init__(self) -> None:
        self._token = os.environ.get("CANOPY_SWITCHBOT_TOKEN")
        self._secret = os.environ.get("CANOPY_SWITCHBOT_SECRET")
        self._session: aiohttp.ClientSession | None = None

    async def connect(self, room: Room) -> None:
        pass  # session created lazily and shared across every room, see _get_session

    async def disconnect(self, room: Room) -> None:
        pass  # shared session; never torn down per-room, same as every other adapter

    async def read(self, room: Room) -> dict[str, float]:
        if not self._token or not self._secret:
            raise RuntimeError("switchbot adapter requires CANOPY_SWITCHBOT_TOKEN and CANOPY_SWITCHBOT_SECRET to be set")
        device_id = room.adapter_config.get("device_id")
        if not device_id:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.device_id")

        session = self._get_session()
        headers = sign_headers(self._token, self._secret)
        async with session.get(f"{API_BASE}/devices/{device_id}/status", headers=headers) as resp:
            body = await resp.json(content_type=None)
            if resp.status != 200 or body.get("statusCode") != 100:
                raise RuntimeError(f"SwitchBot status request for device '{device_id}' failed: {body}")

        return _parse_status(body["body"])

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS))
        return self._session


def sign_headers(token: str, secret: str) -> dict[str, str]:
    """SwitchBot's documented request-signing recipe, split out so it's directly
    unit-testable against a known input/output pair without a network call."""
    t = str(int(time.time() * 1000))
    nonce = str(uuid.uuid4())
    string_to_sign = f"{token}{t}{nonce}"
    sign = base64.b64encode(hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest())
    return {
        "Authorization": token,
        "sign": sign.decode("utf-8"),
        "t": t,
        "nonce": nonce,
        "Content-Type": "application/json; charset=utf8",
    }


def _parse_status(body: dict[str, Any]) -> dict[str, float]:
    """Split out from the HTTP call so response parsing is directly unit-testable.
    Only maps fields this adapter is actually confident about the shape of — Meter/
    MeterPlus/Hub2's temperature+humidity, per SwitchBot's public API docs. Plug
    power monitoring isn't included: SwitchBot's plug status response reports
    on/off state, not a confirmed wattage field, and this shouldn't guess at a shape
    that hasn't been verified against a real response."""
    values: dict[str, float] = {}
    if "temperature" in body:
        values["temp_f"] = body["temperature"] * 9 / 5 + 32  # see CELSIUS_DEVICE_TYPES_NOTE
    if "humidity" in body:
        values["rh_pct"] = float(body["humidity"])
    return values
