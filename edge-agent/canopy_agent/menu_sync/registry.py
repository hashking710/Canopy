import logging
import os
from importlib.metadata import EntryPoint, entry_points

from canopy_agent.menu_sync.base import MenuSync
from canopy_agent.menu_sync.null_sync import NullMenuSync

logger = logging.getLogger("canopy_agent.menu_sync.registry")

# Same shape as compliance_sync/registry.py, and for the same reason: a POS/menu
# target is exactly the "many possible, don't want to maintain them all" situation
# sensor adapters and compliance sync already are. "null" is the only implementation
# this package ships itself; real ones (a POS, Weedmaps) arrive as separately
# installed plugin packages. Selected via CANOPY_MENU_SYNC (defaults to "null" — no
# external push until configured).
PLUGIN_GROUP = "canopy.menu_sync"

_instance: MenuSync | None = None
_factories: dict[str, type[MenuSync]] | None = None


def _load_factories() -> dict[str, type[MenuSync]]:
    global _factories
    if _factories is not None:
        return _factories

    factories: dict[str, type[MenuSync]] = {"null": NullMenuSync}
    for ep in entry_points(group=PLUGIN_GROUP):
        _register_plugin(factories, ep)
    _factories = factories
    return factories


def _register_plugin(factories: dict[str, type[MenuSync]], ep: EntryPoint) -> None:
    try:
        sync_cls = ep.load()
    except Exception:
        logger.exception("failed to load menu sync plugin '%s' — skipping it", ep.name)
        return

    if not (isinstance(sync_cls, type) and issubclass(sync_cls, MenuSync)):
        logger.error("menu sync plugin '%s' does not point at a MenuSync subclass — skipping it", ep.name)
        return

    if ep.name in factories:
        logger.warning("menu sync plugin '%s' conflicts with an existing sync type — skipping it", ep.name)
        return

    factories[ep.name] = sync_cls


def available_sync_types() -> dict[str, type[MenuSync]]:
    """sync_type -> class, for anything that wants to list/describe what's
    installed (mirrors compliance_sync.registry.available_sync_types)."""
    return dict(_load_factories())


def get_menu_sync() -> MenuSync:
    global _instance
    if _instance is None:
        sync_type = os.environ.get("CANOPY_MENU_SYNC", "null")
        factories = _load_factories()
        factory = factories.get(sync_type)
        if factory is None:
            raise ValueError(
                f"unknown CANOPY_MENU_SYNC '{sync_type}' (installed: {sorted(factories)}) — "
                "is the plugin package installed?"
            )
        _instance = factory()
    return _instance
