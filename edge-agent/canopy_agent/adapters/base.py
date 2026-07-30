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
    #: Optional hint for what `Room.adapter_config` needs, e.g. {"dev_id": "controller ID from the vendor app"}.
    #: Purely descriptive — not validated — but lets a future config UI explain itself.
    config_schema: ClassVar[dict[str, str]] = {}
    #: Optional hint for env vars this adapter reads directly (credentials shared across
    #: every room using it, e.g. {"CANOPY_GOVEE_API_KEY": "API key from the Govee Home app"}) —
    #: as opposed to config_schema, which is per-room. Purely descriptive, same as config_schema;
    #: surfaced in the room-creation UI so picking this adapter doesn't silently need a second,
    #: invisible setup step outside the app.
    required_env_vars: ClassVar[dict[str, str]] = {}

    @abstractmethod
    async def connect(self, room: Room) -> None: ...

    @abstractmethod
    async def read(self, room: Room) -> dict[str, float]:
        """Return {metric_key: value} for every non-derived metric in room.metric_config."""
        ...

    @abstractmethod
    async def disconnect(self, room: Room) -> None: ...
