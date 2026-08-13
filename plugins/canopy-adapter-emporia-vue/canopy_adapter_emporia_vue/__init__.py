"""
Emporia Vue — whole-panel power monitoring, via Emporia's real cloud API.

Emporia's cloud authenticates via AWS Cognito SRP (Secure Remote Password), a real
challenge-response cryptographic protocol — genuinely too risky to hand-roll from
memory (see docs/architecture.md's prior note on why this adapter didn't exist yet).
Built instead on `pycognito` (PyPI: pycognito, MIT licensed, depends on `boto3` and
`pyjwt`), a real, independently maintained SRP/Cognito client — the auth handshake
itself is entirely that vetted library's responsibility, not reimplemented here.

Confidence note: the Cognito user pool ID (`us-east-2_ghlOXVLi1`) and app client ID
(`4qte47jbstod8apnfic0bunmrq`) below, the `AppAPI?apiMethod=getDeviceListUsages`
endpoint shape, and the kWh-at-1-second-scale-to-watts conversion are all taken
directly from reading the real source of `magico13/PyEmVue` (PyPI: pyemvue, MIT
licensed, v0.18.9 — a mature, actively used library, not a forum thread), fetched and
read directly rather than reconstructed from memory. The `usage * 3600 * 1000`
watts conversion is independently corroborated by a second, unrelated project
(mcsMQTT, a HomeSeer plugin) using the same formula. This adapter deliberately
doesn't depend on `pyemvue` itself, for the same reason every other cloud adapter in
this ecosystem hand-rolls its own HTTP calls with aiohttp rather than wrapping a
third-party client library wholesale (see e.g. canopy-adapter-govee,
canopy-adapter-switchbot) — `pycognito` is used only for the genuinely hard
cryptographic part, matching canopy-adapter-tuya's `tinytuya` dependency for AES.
Real hardware/account verification is still warranted before trusting production
values — this has not been tested against a real Emporia Vue device.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import ClassVar

import aiohttp
from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room
from pycognito import Cognito

REQUEST_TIMEOUT_SECONDS = 10

API_ROOT = "https://api.emporiaenergy.com"
API_DEVICES_USAGE_PATH = "AppAPI"

# Emporia's own AWS Cognito app, from magico13/PyEmVue's auth.py — the same pool/
# client every Emporia Vue app and integration authenticates against; there is no
# per-user or per-account pool.
COGNITO_USER_POOL_ID = "us-east-2_ghlOXVLi1"
COGNITO_CLIENT_ID = "4qte47jbstod8apnfic0bunmrq"
COGNITO_USER_POOL_REGION = "us-east-2"


class EmporiaVueAdapter(SensorAdapter):
    """
    room.adapter_config shape:
        {
          "device_gid": "123456",   # from Emporia's device list (see the app, or
                                     # GET customers/devices once logged in)
          "channel_num": "1,2,3"    # "1,2,3" for the whole panel/mains, or a single
                                     # breaker's own channel number
        }

    Reports power_w only — instantaneous power, derived from Emporia's 1-second-scale
    kWh usage figure (see _watts_from_kwh_1s).
    """

    plugin_name = "Emporia Vue (whole-panel power monitoring)"
    plugin_description = (
        "Whole-panel or per-breaker power monitoring via Emporia's cloud API — AWS "
        "Cognito login through the vetted pycognito library, not a hand-rolled auth "
        "handshake."
    )
    category: ClassVar[str] = "cloud"
    required_env_vars: ClassVar[dict[str, str]] = {
        "CANOPY_EMPORIA_EMAIL": "Email for your Emporia Vue account",
        "CANOPY_EMPORIA_PASSWORD": "Password for your Emporia Vue account",
    }
    config_schema: ClassVar[dict[str, str]] = {
        "device_gid": "Device GID from Emporia's device list (numeric ID)",
        "channel_num": "Channel to read — '1,2,3' for the whole panel/mains, or a single breaker's own channel number",
    }
    default_metric_config: ClassVar[dict[str, dict]] = {
        "power_w": {"label": "power", "unit": "W", "decimals": 1},
    }

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._id_token: str | None = None
        # Tracks which (email, password) the cached id_token was obtained with —
        # same hot-reload pattern as canopy-adapter-ac-infinity's _logged_in_with:
        # credentials are read fresh from os.environ every read() (not cached at
        # __init__, since one adapter instance is shared across the process's whole
        # lifetime — see adapters/registry.py), so a dashboard-set credential change
        # forces a real re-login rather than silently continuing to use a stale token.
        self._logged_in_with: tuple[str | None, str | None] = (None, None)

    async def connect(self, room: Room) -> None:
        pass  # session/login are created lazily and shared across every room, see read()

    async def disconnect(self, room: Room) -> None:
        pass  # shared session/login; never torn down per-room, same as every other adapter

    async def read(self, room: Room) -> dict[str, float]:
        config = room.adapter_config
        device_gid = config.get("device_gid")
        if not device_gid:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.device_gid")
        channel_num = config.get("channel_num")
        if not channel_num:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.channel_num")

        email = os.environ.get("CANOPY_EMPORIA_EMAIL")
        password = os.environ.get("CANOPY_EMPORIA_PASSWORD")
        if not email or not password:
            raise RuntimeError(
                f"room '{room.id}': adapter 'emporia_vue' requires "
                f"CANOPY_EMPORIA_EMAIL and CANOPY_EMPORIA_PASSWORD to be set"
            )

        await self._ensure_logged_in(email, password)
        body = await self._request_usage(str(device_gid))
        watts = extract_channel_watts(body, str(device_gid), str(channel_num))
        if watts is None:
            raise RuntimeError(
                f"room '{room.id}': no channel '{channel_num}' found for device_gid "
                f"'{device_gid}' in Emporia's usage response"
            )
        return {"power_w": watts}

    async def _ensure_logged_in(self, email: str, password: str) -> None:
        if self._id_token is not None and self._logged_in_with == (email, password):
            return
        await self._login(email, password)

    async def _login(self, email: str, password: str) -> None:
        # pycognito's Cognito.authenticate() performs the real SRP handshake via
        # boto3 — synchronous, CPU/network-bound AWS SDK calls, so it's run off the
        # event loop rather than blocking every other room's poll.
        cognito = Cognito(
            COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID, user_pool_region=COGNITO_USER_POOL_REGION, username=email
        )
        await asyncio.to_thread(cognito.authenticate, password=password)
        self._id_token = cognito.id_token
        self._logged_in_with = (email, password)

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS))
        return self._session

    async def _request_usage(self, device_gid: str) -> dict:
        session = self._get_session()
        params = {
            "apiMethod": "getDeviceListUsages",
            "deviceGids": device_gid,
            "instant": _format_instant(datetime.now(timezone.utc)),
            "scale": "1S",
            "energyUnit": "KilowattHours",
        }
        status, body = await self._do_usage_request(session, params)
        if status == 401:
            # id_token expired/invalid — force a fresh login and retry exactly once,
            # same "retry once on 401, don't loop forever" shape as
            # canopy-adapter-rainmachine's token handling.
            await self._login(*self._logged_in_with)
            status, body = await self._do_usage_request(session, params)
        if status != 200 or body is None:
            raise RuntimeError(f"Emporia Vue usage request returned HTTP {status}")
        return body

    async def _do_usage_request(self, session: aiohttp.ClientSession, params: dict) -> tuple[int, dict | None]:
        url = f"{API_ROOT}/{API_DEVICES_USAGE_PATH}"
        async with session.get(url, params=params, headers={"authtoken": self._id_token or ""}) as resp:
            if resp.status != 200:
                return resp.status, None
            return resp.status, await resp.json(content_type=None)


def _format_instant(moment: datetime) -> str:
    """Matches PyEmVue's own pyemvue.py:_format_time exactly — an isoformat
    timestamp with no explicit UTC offset, suffixed with a literal "Z"."""
    return moment.astimezone(timezone.utc).replace(tzinfo=None).isoformat() + "Z"


def extract_channel_watts(usage_response: dict, device_gid: str, channel_num: str) -> float | None:
    """Pure — fully unit-testable against a constructed response shape without a
    real API call. `usage_response` is the raw JSON body of a
    getDeviceListUsages response; `usage` on the matching channel is a kWh figure
    for the requested 1-second scale window, converted to instantaneous watts via
    watts = kwh * 3600 * 1000 (see module docstring for the corroborating sources).
    Returns None if the device_gid/channel_num combination isn't present in the
    response (e.g. a typo'd channel_num, or the device went offline)."""
    devices = (usage_response.get("deviceListUsages") or {}).get("devices") or []
    for device in devices:
        if str(device.get("deviceGid")) != device_gid:
            continue
        for channel in device.get("channelUsages") or []:
            if channel is None:
                continue
            if str(channel.get("channelNum")) == channel_num:
                usage_kwh = channel.get("usage")
                if usage_kwh is None:
                    return None
                return usage_kwh * 3600 * 1000
    return None
