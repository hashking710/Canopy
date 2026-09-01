from canopy_agent.menu_sync.base import MenuSync


class NullMenuSync(MenuSync):
    """Default: pushes nothing anywhere. Canopy's own database is the only system
    of record until a real MenuSync (a POS integration, Weedmaps, ...) is
    configured via CANOPY_MENU_SYNC."""

    plugin_name = "None (built-in)"
    plugin_description = "Inventory/genetics data stays in Canopy only — nothing is pushed to a POS or menu."

    async def push_menu(self, items: list[dict]) -> dict:
        return {"pushed": 0, "skipped": len(items)}
