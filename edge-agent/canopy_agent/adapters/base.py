from abc import ABC, abstractmethod
from typing import ClassVar

from canopy_agent.models import Room


class SensorAdapter(ABC):
    """
    Common interface for anything that can produce readings for a room — mocked data,
    a third-party plugin talking to real hardware, whatever. Swapping the adapter a
    room uses should never require changes to the poller, storage, or API; that
    boundary is also what lets adapters ship as separate, independently maintained
    plugin packages (see adapters/registry.py and docs/plugin-development.md) instead
    of living in this codebase.
    """

    #: Shown in plugin listings / error messages. Override in subclasses.
    plugin_name: ClassVar[str] = "unnamed adapter"
    plugin_description: ClassVar[str] = ""
    #: Groups the room-creation UI's adapter picker so someone with, say, a Govee
    #: sensor isn't scanning ~16 flat, similarly-terse options to find it — one of
    #: "cloud" (needs a vendor account/API key), "local" (talks to a device on your
    #: LAN, no cloud account), "bluetooth", "hardware" (direct-attached Pi GPIO/I2C),
    #: or "testing" (the built-in mock). Purely descriptive/cosmetic, same spirit as
    #: config_schema; an unrecognized value just falls back to its own group.
    category: ClassVar[str] = "other"
    #: Optional hint for what `Room.adapter_config` needs, e.g. {"dev_id": "controller ID from the vendor app"}.
    #: Purely descriptive — not validated — but lets a future config UI explain itself.
    config_schema: ClassVar[dict[str, str]] = {}
    #: Optional hint for env vars this adapter reads directly (credentials shared across
    #: every room using it, e.g. {"CANOPY_GOVEE_API_KEY": "API key from the Govee Home app"}) —
    #: as opposed to config_schema, which is per-room. Purely descriptive, same as config_schema;
    #: surfaced in the room-creation UI so picking this adapter doesn't silently need a second,
    #: invisible setup step outside the app.
    required_env_vars: ClassVar[dict[str, str]] = {}
    #: Optional starting point for Room.metric_config, in the same shape
    #: ({metric_key: {"label": ..., "unit": ..., "decimals": ...}}) — for an adapter with
    #: a fixed, predictable set of readings (e.g. Govee always reports temp_f/rh_pct),
    #: lets the room-creation UI pre-fill the metric editor instead of making every user
    #: retype the exact keys the adapter's own read() already returns. Left empty for
    #: adapters whose metrics are inherently user-defined (Modbus registers, MQTT
    #: topics, BLE byte layouts, GPIO's per-kind sensors) — nothing to sensibly default
    #: there. Purely a UI convenience; the user can still edit/remove rows afterward.
    default_metric_config: ClassVar[dict[str, dict]] = {}

    @abstractmethod
    async def connect(self, room: Room) -> None: ...

    @abstractmethod
    async def read(self, room: Room) -> dict[str, float]:
        """Return {metric_key: value} for every non-derived metric in room.metric_config."""
        ...

    @abstractmethod
    async def disconnect(self, room: Room) -> None: ...
