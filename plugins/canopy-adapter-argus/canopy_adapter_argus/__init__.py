from typing import ClassVar

from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room

# Sourced directly from Argus Controls' own official "Titan Operator Program 900
# Series" datasheet (arguscontrols.com, a real PDF, read directly — not recalled
# from memory). Confirmed real, in the vendor's own words:
#   - "Argus API OUT allows access to our data from an external source"
#   - "API Out only: users can only retrieve information (GET only) from their own
#     system to use for data analysis"
#   - "Authentication: A Username and Password are required. User Privileges are
#     required before using the API."
#   - "data is returned in a string (date/time, parameter, data)"
#   - Requires a Titan 900-series gateway (Build 900+) on the local network.
#
# NOT confirmed anywhere in this datasheet or any other reachable public source: the
# actual request path, exact auth mechanism (HTTP Basic? a login endpoint issuing a
# session token? the datasheet doesn't say), or the precise format of the returned
# "string." This is a marketing datasheet, not a technical API reference — same
# category of source as canopy-adapter-trolmaster's own pricing/signup page, and
# held to the same bar: real functionality confirmed to exist, exact protocol not
# guessed at.


class ArgusAdapter(SensorAdapter):
    """
    Argus Controls (Titan/Axia) climate computers — a real GET-only local API
    confirmed to exist on Titan 900-series gateways, but this adapter can't be
    finished without direct access to Argus's technical API reference (not publicly
    published — see this module's own top-of-file comment) or a real gateway to
    reverse-engineer against.
    """

    plugin_name = "Argus Controls (Titan/Axia)"
    plugin_description = (
        "Argus Controls Titan/Axia climate computers — a real GET-only local API "
        "exists on Titan 900-series gateways, but this adapter's read() isn't "
        "implemented yet: Argus's technical API reference isn't publicly published. "
        "See this plugin's own module docstring."
    )
    category: ClassVar[str] = "local"
    config_schema: ClassVar[dict[str, str]] = {
        "host": "Titan 900-series gateway IP/hostname on your LAN",
        "username": "Argus API username (requires User Privileges enabled by your Argus administrator)",
        "password": "Argus API password",
        "parameter": "Argus parameter name for this room's sensor point (once a real gateway confirms the exact format)",
    }

    async def connect(self, room: Room) -> None:
        pass

    async def disconnect(self, room: Room) -> None:
        pass

    async def read(self, room: Room) -> dict[str, float]:
        config = room.adapter_config
        if not config.get("host"):
            raise RuntimeError(f"room '{room.id}' has no adapter_config.host")
        if not (config.get("username") and config.get("password")):
            raise RuntimeError(f"room '{room.id}' needs both adapter_config.username and adapter_config.password")

        raise NotImplementedError(
            "Argus Controls' Titan/Axia API (GET-only, username/password-authenticated, "
            "confirmed real via their own official datasheet) has no publicly published "
            "endpoint reference — direct contact with Argus support, or access to a real "
            "Titan 900-series gateway to inspect against, is needed to confirm the exact "
            "request path and response format before this can be finished — see this "
            "module's own docstring."
        )
