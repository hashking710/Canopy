from abc import ABC, abstractmethod
from typing import ClassVar


class MenuSync(ABC):
    """
    Interface for pushing the current sellable-inventory snapshot (see
    services/menu_data.py's build_menu_items) out to an external point-of-sale
    system or a menu listing service (Weedmaps, etc). Mirrors
    compliance_sync.base.ComplianceSync on purpose — same plugin shape, same
    "a no-op implementation is the default until real credentials exist to build
    and verify a real one against", same "implementations ship as separate plugin
    packages discovered via menu_sync/registry.py" — but a fundamentally different
    interaction pattern: compliance sync pushes individual lifecycle *events* as
    they happen, menu sync pushes a full point-in-time *snapshot* on an interval
    (see services/menu_sync_task.py), since a menu is "what's currently for sale
    right now", not an event log.
    """

    plugin_name: ClassVar[str] = "unnamed menu sync"
    plugin_description: ClassVar[str] = ""
    config_schema: ClassVar[dict[str, str]] = {}
    #: Same shape/purpose as SensorAdapter.required_env_vars / ComplianceSync's own —
    #: credentials this plugin reads from the environment, surfaced so the dashboard's
    #: credentials settings (routers/secrets.py) can list and set them without
    #: hardcoding knowledge of any specific menu-sync plugin.
    required_env_vars: ClassVar[dict[str, str]] = {}

    @abstractmethod
    async def push_menu(self, items: list[dict]) -> dict:
        """Push the current snapshot. `items` is the list build_menu_items()
        produces — each a dict with package_id/item_name/weight_g/price_cents/
        room_id/strain_name/strain_type/lineage/thc_pct/cbd_pct. Returns a small
        result dict (e.g. {"pushed": N, "skipped": N}) for status reporting —
        implementations decide their own create-vs-update semantics against
        whatever system they're targeting."""
        ...
