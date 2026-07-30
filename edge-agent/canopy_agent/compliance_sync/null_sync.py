from canopy_agent.compliance_sync.base import ComplianceSync


class NullComplianceSync(ComplianceSync):
    """Default: records nothing externally. Canopy's own database is the only system
    of record until a real ComplianceSync (e.g. METRC, once we have credentials to
    verify against) is configured."""

    plugin_name = "None (built-in)"
    plugin_description = "Compliance events stay in Canopy's own database only — nothing is reported externally."

    async def sync_plant_batch_created(self, batch: dict) -> None:
        pass

    async def sync_plant_tagged(self, plant: dict) -> None:
        pass

    async def sync_plant_moved(self, plant: dict, from_room_id: str) -> None:
        pass

    async def sync_plant_destroyed(self, plant: dict, waste: dict) -> None:
        pass

    async def sync_harvest_created(self, harvest: dict) -> None:
        pass

    async def sync_waste_event(self, waste: dict) -> None:
        pass

    async def sync_package_created(self, package: dict) -> None:
        pass
