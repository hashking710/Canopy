from abc import ABC, abstractmethod
from typing import ClassVar


class ComplianceSync(ABC):
    """
    Interface for reporting compliance events to an external track-and-trace system
    (METRC, BioTrackTHC, ...). Mirrors adapters.base.SensorAdapter on purpose: the
    compliance router calls these on every mutating action, a no-op implementation
    (NullComplianceSync) is the default until real credentials exist to build and
    verify a real one against, and implementations ship as separate plugin packages
    discovered via compliance_sync/registry.py rather than living in this codebase —
    see docs/architecture.md and docs/plugin-development.md.
    """

    plugin_name: ClassVar[str] = "unnamed sync"
    plugin_description: ClassVar[str] = ""
    config_schema: ClassVar[dict[str, str]] = {}

    @abstractmethod
    async def sync_plant_batch_created(self, batch: dict) -> None: ...

    @abstractmethod
    async def sync_plant_tagged(self, plant: dict) -> None: ...

    @abstractmethod
    async def sync_plant_moved(self, plant: dict, from_room_id: str) -> None: ...

    @abstractmethod
    async def sync_plant_destroyed(self, plant: dict, waste: dict) -> None: ...

    @abstractmethod
    async def sync_harvest_created(self, harvest: dict) -> None: ...

    @abstractmethod
    async def sync_waste_event(self, waste: dict) -> None: ...

    @abstractmethod
    async def sync_package_created(self, package: dict) -> None: ...
