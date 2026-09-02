import os
from typing import ClassVar

from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room

# Sourced from Pulse Grow's own help-center article ("Pulse API Access",
# support.pulsegrow.com, read directly) — confirmed real: a live API at
# api.pulsegrow.com with published reference docs (api.pulsegrow.com/docs/index.html),
# and API keys generated per-user from within the Pulse app itself (Settings ->
# General Settings -> API -> Add API Key), explicitly described as sensitive like a
# password.
#
# NOT independently confirmed: the reference docs page renders its actual endpoint
# list/schema via client-side JavaScript (a Swagger/OpenAPI-style UI), which this
# project's fetch tooling could not execute — so the exact request header the API
# key goes in, the endpoint paths, and the response shape for a sensor reading are
# all still unknown. Real functionality confirmed to exist, exact protocol not
# guessed at — same posture as canopy-adapter-trolmaster's scaffold.


class PulseGrowAdapter(SensorAdapter):
    """
    Pulse Grow environmental sensors (VPD/CO2/PPFD/spectrum) — a real, documented
    cloud API confirmed to exist at api.pulsegrow.com, but this adapter can't be
    finished without a real API key and account to confirm the exact endpoint
    paths/response shape against (the reference docs are JavaScript-rendered and
    not reachable by this project's research tooling). See this module's own
    top-of-file comment.
    """

    plugin_name = "Pulse Grow"
    plugin_description = (
        "Pulse Grow VPD/CO2/PPFD environmental sensors — a real cloud API exists "
        "(api.pulsegrow.com), but this adapter's read() isn't implemented yet: its "
        "reference docs are JavaScript-rendered and weren't reachable to confirm "
        "the exact request shape. See this plugin's own module docstring."
    )
    category: ClassVar[str] = "cloud"
    config_schema: ClassVar[dict[str, str]] = {
        "device_id": "Pulse Grow device id (once a real account confirms the exact identifier format)",
    }
    required_env_vars: ClassVar[dict[str, str]] = {
        "CANOPY_PULSEGROW_API_KEY": "Pulse Grow API key (Pulse app → Settings → General Settings → API)",
    }

    async def connect(self, room: Room) -> None:
        pass

    async def disconnect(self, room: Room) -> None:
        pass

    async def read(self, room: Room) -> dict[str, float]:
        if not os.environ.get("CANOPY_PULSEGROW_API_KEY"):
            raise RuntimeError("pulsegrow adapter requires CANOPY_PULSEGROW_API_KEY to be set")
        if not room.adapter_config.get("device_id"):
            raise RuntimeError(f"room '{room.id}' has no adapter_config.device_id")

        raise NotImplementedError(
            "Pulse Grow's API reference (api.pulsegrow.com/docs/index.html) renders "
            "via client-side JavaScript and wasn't reachable to confirm the exact "
            "request shape. A real Pulse Grow account and API key are needed to "
            "confirm the endpoint paths and response format before this can be "
            "finished — see this module's own docstring."
        )
