import os
from typing import ClassVar

from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room

# Sourced from web search of Growlink's own public developer materials — confirmed
# real: a public developer portal at developer.growlink.com, built on Microsoft
# Azure API Management (same platform Priva's developer portal uses — a real,
# vendor-sanctioned REST/JSON API, cannabis-cultivation-specific, not a hobbyist
# integration). Confirmed generically: Bearer-token authentication in the
# Authorization header.
#
# NOT independently confirmed, and this class is honest about that rather than
# guessing: the exact endpoint paths, the token-acquisition mechanism (a static API
# key vs. an OAuth2 flow — Azure APIM supports either, and the portal's homepage
# doesn't specify which Growlink chose), and the response shape for reading a
# sensor's current value. The portal requires a developer-account signup to reach
# the actual reference documentation. `read()` raises NotImplementedError naming
# exactly what's needed to finish this — same posture as
# canopy-adapter-trolmaster's scaffold.


class GrowlinkAdapter(SensorAdapter):
    """
    Growlink cultivation controllers/sensors — a real, cannabis-specific cloud
    platform with a public developer portal (developer.growlink.com), but this
    adapter can't be finished without a real developer-account signup to confirm
    the exact endpoint paths and response shape. See this module's own top-of-file
    comment.
    """

    plugin_name = "Growlink"
    plugin_description = (
        "Growlink cultivation controllers/sensors — has a real, cannabis-specific "
        "developer API (developer.growlink.com), but this adapter's read() isn't "
        "implemented yet: the exact endpoint shape needs a real developer-account "
        "signup to confirm. See this plugin's own module docstring."
    )
    category: ClassVar[str] = "cloud"
    config_schema: ClassVar[dict[str, str]] = {
        "device_id": "Growlink device/sensor id (once a real account confirms the exact identifier format)",
    }
    required_env_vars: ClassVar[dict[str, str]] = {
        "CANOPY_GROWLINK_API_KEY": "Growlink developer-portal API key/token (developer.growlink.com)",
    }

    async def connect(self, room: Room) -> None:
        pass

    async def disconnect(self, room: Room) -> None:
        pass

    async def read(self, room: Room) -> dict[str, float]:
        if not os.environ.get("CANOPY_GROWLINK_API_KEY"):
            raise RuntimeError("growlink adapter requires CANOPY_GROWLINK_API_KEY to be set")
        if not room.adapter_config.get("device_id"):
            raise RuntimeError(f"room '{room.id}' has no adapter_config.device_id")

        raise NotImplementedError(
            "Growlink's developer API (developer.growlink.com) has no publicly "
            "reachable endpoint reference — its Azure API Management portal requires "
            "a developer-account signup to view. A real Growlink account is needed to "
            "confirm the exact request/response shape before this can be finished — "
            "see this module's own docstring."
        )
