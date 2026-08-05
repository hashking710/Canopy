import os
import time

import aiohttp
from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room

HOST = "http://www.acinfinityserver.com"
LOGIN_PATH = "/api/user/appUserLogin"
DEVICE_LIST_PATH = "/api/user/devInfoListAll"
USER_AGENT = "okhttp/4.12.0"

# Keep the shared controller-list cache a bit under the poll interval so every poll
# cycle sees fresh data, while N rooms on one account still cost 1 HTTP call, not N.
CONTROLLER_CACHE_SECONDS = 4


class ACInfinityCloudAdapter(SensorAdapter):
    """
    Polls AC Infinity's cloud API for WiFi-connected UIS controllers (Controller 69
    WiFi/Pro/Pro+, AI+). NOT for Bluetooth-only controllers (base 69, Controller 67) —
    those never sync to AC Infinity's cloud and need a separate BLE adapter.

    AC Infinity does not publish a public API. The endpoints, request shapes, and field
    scaling below are reverse-engineered, sourced from the maintained open-source Home
    Assistant integration (github.com/dalinicus/homeassistant-acinfinity/blob/main/
    custom_components/ac_infinity/{client.py,const.py,sensor.py}), not from official
    docs or a device we've tested against ourselves. Verify against a real account
    before relying on it — a login or field-shape change on AC Infinity's end would
    surface here as a RuntimeError from _login/_get_account_controllers.

    Each room using this adapter needs `room.adapter_config = {"dev_id": "<controller devId>"}`
    (the id AC Infinity's app shows for that controller). Credentials are shared across
    every room on this adapter — one AC Infinity account, read once from
    CANOPY_AC_INFINITY_EMAIL / CANOPY_AC_INFINITY_PASSWORD.

    This is a separately packaged, separately versioned plugin — see
    docs/plugin-development.md in the Canopy repo for how adapters like this one plug
    into the core app without living in its codebase.
    """

    plugin_name = "AC Infinity (Cloud/WiFi)"
    plugin_description = (
        "For WiFi-connected UIS controllers (69 WiFi/Pro/Pro+, AI+). Not for "
        "Bluetooth-only controllers — see the community BLE thread linked in "
        "docs/architecture.md for that gap."
    )
    category = "cloud"
    config_schema = {"dev_id": "Controller ID as shown in the AC Infinity app"}
    required_env_vars = {
        "CANOPY_AC_INFINITY_EMAIL": "Your AC Infinity account email",
        "CANOPY_AC_INFINITY_PASSWORD": "Your AC Infinity account password",
    }
    default_metric_config = {
        "temp_f": {"label": "temp", "unit": "°F", "decimals": 1},
        "rh_pct": {"label": "RH", "unit": "%", "decimals": 1},
        "vpd_kpa": {"label": "VPD", "unit": "kPa", "decimals": 2},
    }

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._user_id: str | None = None
        # Which (email, password) the cached _user_id session was established
        # with — compared against the freshly-read env vars on every call so a
        # credential changed through the dashboard (routers/secrets.py) forces a
        # real re-login instead of silently continuing to use a session
        # authenticated under the old, now-stale credentials.
        self._logged_in_with: tuple[str | None, str | None] = (None, None)
        self._controllers_by_dev_id: dict[str, dict] = {}
        self._controllers_fetched_at: float = 0.0

    async def connect(self, room: Room) -> None:
        pass  # login is lazy, on first read()

    async def disconnect(self, room: Room) -> None:
        pass  # session is shared across rooms; nothing to tear down per-room

    async def read(self, room: Room) -> dict[str, float]:
        # Read fresh on every call, not cached at __init__: this adapter instance
        # is long-lived and shared across every room using it
        # (adapters/registry.py), so a credential set through the dashboard must
        # take effect on the very next poll cycle, not only after a restart.
        email = os.environ.get("CANOPY_AC_INFINITY_EMAIL")
        password = os.environ.get("CANOPY_AC_INFINITY_PASSWORD")
        if not email or not password:
            raise RuntimeError(
                "ac_infinity_cloud adapter requires CANOPY_AC_INFINITY_EMAIL and "
                "CANOPY_AC_INFINITY_PASSWORD to be set"
            )
        dev_id = str(room.adapter_config.get("dev_id", ""))
        if not dev_id:
            raise RuntimeError(f"room '{room.id}' has no adapter_config.dev_id")

        await self._ensure_controllers_fresh(email, password)
        controller = self._controllers_by_dev_id.get(dev_id)
        if controller is None:
            raise RuntimeError(f"AC Infinity account has no controller with devId={dev_id}")

        # Values come back as integers representing a 2-digit-precision float, always in
        # Celsius/kPa regardless of the controller's display unit (see sensor.py's
        # __get_value_fn_floating_point_as_int in the reference integration above).
        temp_c = controller.get("temperature", 0) / 100
        return {
            "temp_f": temp_c * 9 / 5 + 32,
            "rh_pct": controller.get("humidity", 0) / 100,
            "vpd_kpa": controller.get("vpdnums", 0) / 100,
        }

    async def _ensure_controllers_fresh(self, email: str, password: str) -> None:
        if time.monotonic() - self._controllers_fetched_at < CONTROLLER_CACHE_SECONDS:
            return
        session = self._get_session()
        if self._user_id is None or self._logged_in_with != (email, password):
            await self._login(session, email, password)
            self._logged_in_with = (email, password)
        controllers = await self._get_account_controllers(session)
        self._controllers_by_dev_id = {str(c["devId"]): c for c in controllers}
        self._controllers_fetched_at = time.monotonic()

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _login(self, session: aiohttp.ClientSession, email: str, password: str) -> None:
        # AC Infinity's API rejects passwords over 25 characters; their apps silently
        # truncate on submit, so we must match that or a correct password will "fail".
        truncated_password = password[:25]
        async with session.post(
            f"{HOST}{LOGIN_PATH}",
            data={"appEmail": email, "appPasswordl": truncated_password},
            headers={"User-Agent": USER_AGENT},
        ) as resp:
            body = await resp.json(content_type=None)
            if resp.status != 200 or body.get("code") != 200:
                raise RuntimeError(f"AC Infinity login failed: {body}")
            self._user_id = body["data"]["appId"]

    async def _get_account_controllers(self, session: aiohttp.ClientSession) -> list[dict]:
        async with session.post(
            f"{HOST}{DEVICE_LIST_PATH}",
            data={"userId": self._user_id},
            headers={"User-Agent": USER_AGENT, "token": self._user_id},
        ) as resp:
            body = await resp.json(content_type=None)
            if resp.status != 200 or body.get("code") != 200:
                self._user_id = None  # force a re-login next cycle; token may have expired
                raise RuntimeError(f"AC Infinity device list request failed: {body}")
            return body["data"]
