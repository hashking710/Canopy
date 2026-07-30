from typing import ClassVar

from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.models import Room


class TrolMasterCloudAdapter(SensorAdapter):
    """
    NOT YET FUNCTIONAL — blocked on real API access, not a code problem.

    TrolMaster (Hydro-X/Aqua-X/Carbon-X) was identified by hardware-landscape research
    as the best next plugin target: real commercial-tier market presence (distinct from
    hobbyist brands like AC Infinity, per independent retailer/dealer sourcing), and —
    unlike most of the enterprise-tier competitors surveyed — TrolMaster runs an
    official, vendor-sanctioned API Gateway program rather than requiring reverse-
    engineering. See docs/architecture.md for the full research.

    That program is signup-gated and paid ($15/month/device per TrolMaster's own
    support article), and a direct fetch of its documentation page 403'd (Zendesk
    blocking automated access) — so unlike the AC Infinity plugin, which was built
    against a maintained open-source reverse-engineering project with real, verified
    endpoint shapes, there was nothing concrete here to implement against. Guessing
    request/response shapes would mean shipping an adapter nobody has confirmed works
    against a real device — exactly the kind of unverified claim this project is
    trying to stop making (see the METRC compliance-deadline correction in
    docs/architecture.md for why that matters here).

    To finish this adapter: sign up for TrolMaster's API Gateway program against a real
    device, capture the actual request/response shapes it returns, confirm whether the
    API supports setpoint control or sensor data only (unconfirmed from public pages),
    and replace read() below with a real implementation — the same way
    plugins/canopy-adapter-ac-infinity was built once dalinicus's reverse-engineering
    existed to build against.

    This package still registers as a real plugin (`trolmaster_cloud` in
    `canopy.sensor_adapters`) so the plugin mechanism itself is demonstrable and the
    config shape is documented — it just can't do anything real yet.
    """

    plugin_name = "TrolMaster (Cloud API) — not yet functional"
    plugin_description = (
        "Scaffolded, not implemented — TrolMaster's official API Gateway is signup/"
        "paid-gated with no public endpoint documentation found. See this package's "
        "module docstring and docs/architecture.md before using."
    )
    config_schema: ClassVar[dict[str, str]] = {
        "device_id": "TrolMaster device ID as shown in the TrolMaster app (once the real API is built)",
    }

    async def connect(self, room: Room) -> None:
        pass

    async def disconnect(self, room: Room) -> None:
        pass

    async def read(self, room: Room) -> dict[str, float]:
        raise NotImplementedError(
            "trolmaster_cloud is not implemented yet — it's blocked on real API Gateway "
            "access (paid, signup-gated, no public docs found). See this package's "
            "module docstring for what's needed to finish it. Don't set a room's "
            "adapter_type to 'trolmaster_cloud' expecting real readings."
        )
