import os
import time
from typing import ClassVar

import aiohttp
from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room

REQUEST_TIMEOUT_SECONDS = 15
TOKEN_URL = "https://auth.priva.com/connect/token"
TOKEN_REFRESH_MARGIN_SECONDS = 60

# Sourced from Priva's own public docs (priva.com/buildings, apiportal.priva.com,
# support.priva.com articles, via web search) — confirmed: OAuth2/OIDC client-
# credentials against `https://auth.priva.com/connect/token`, subsequent calls carry
# a JWT Bearer token, and a "Realtime Data API" (telemetry + setpoint control) exists
# as a paid add-on on top of the base subscription, with Change-of-Value push via a
# customer's own Azure EventHub alongside a pull-style telemetry read.
#
# NOT independently confirmed, and this class is honest about that rather than
# guessing: the exact telemetry-read REST path and response shape. Priva's API is
# also architecturally per-customer — `apiportal.priva.com` is the docs portal, not
# necessarily the API host itself, and per-site OAuth2 client registration (via
# Priva's own Access Control App) means each customer's actual API base URL and
# reference/tag naming is provisioned individually, not a fixed constant this
# package could hardcode even if the path shape were confirmed. `read()` therefore
# implements the real, confirmed OAuth2 token acquisition, then raises
# NotImplementedError for the telemetry call itself, naming exactly what's needed
# (a real Priva account's provisioned API base URL and reference documentation) to
# finish it — same posture as canopy-adapter-trolmaster's scaffold.


class PrivaAdapter(SensorAdapter):
    """
    Priva Building Automation Realtime Data API — enterprise greenhouse climate
    computers. See this module's own top-of-file comment for exactly what's
    confirmed vs. not.

    room.adapter_config shape (once a real account's API paths are confirmed):
        {"reference_id": "<Priva reference/tag id for this room's sensor point>"}
    """

    plugin_name = "Priva"
    plugin_description = (
        "Priva Building Automation climate computers, via the Priva Realtime Data "
        "API — requires a Priva account with the Realtime Data API add-on and a "
        "registered OAuth2 client. See this plugin's own module docstring: the "
        "telemetry-read endpoint isn't implemented yet pending a real account to "
        "confirm its request shape against."
    )
    category: ClassVar[str] = "cloud"
    config_schema: ClassVar[dict[str, str]] = {
        "reference_id": "Priva reference/tag id for this room's sensor point (from your Priva Access Control App)",
    }
    required_env_vars: ClassVar[dict[str, str]] = {
        "CANOPY_PRIVA_CLIENT_ID": "Priva OAuth2 client id (registered in Priva's Access Control App)",
        "CANOPY_PRIVA_CLIENT_SECRET": "Priva OAuth2 client secret",
        "CANOPY_PRIVA_API_BASE_URL": "Your account's provisioned Priva API base URL (per-customer, from your Priva onboarding)",
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
        """The real, confirmed part of this integration — see module docstring."""
        if self._token is not None and time.monotonic() < self._token_expires_at:
            return self._token

        client_id = os.environ.get("CANOPY_PRIVA_CLIENT_ID")
        client_secret = os.environ.get("CANOPY_PRIVA_CLIENT_SECRET")
        if not (client_id and client_secret):
            raise RuntimeError("priva adapter requires CANOPY_PRIVA_CLIENT_ID and CANOPY_PRIVA_CLIENT_SECRET")

        session = self._get_session()
        async with session.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Priva token request returned HTTP {resp.status}: {text[:300]}")
            data = await resp.json(content_type=None)

        self._token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        self._token_expires_at = time.monotonic() + expires_in - TOKEN_REFRESH_MARGIN_SECONDS
        return self._token

    async def read(self, room: Room) -> dict[str, float]:
        if not os.environ.get("CANOPY_PRIVA_API_BASE_URL"):
            raise RuntimeError("priva adapter requires CANOPY_PRIVA_API_BASE_URL to be set")
        reference_id = room.adapter_config.get("reference_id")
        if not reference_id:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.reference_id")

        # Acquiring a real token first, since that part IS confirmed — a
        # misconfigured client id/secret should surface as that specific failure,
        # not get masked by the NotImplementedError below.
        await self._get_token()

        raise NotImplementedError(
            "Priva's Realtime Data API telemetry-read endpoint has no confirmed public "
            "request shape — apiportal.priva.com's reference documentation is behind a "
            "per-account developer portal login. A real Priva account (with the "
            "Realtime Data API add-on) is needed to confirm the exact path and response "
            "shape before this can be finished — see this module's own docstring."
        )
