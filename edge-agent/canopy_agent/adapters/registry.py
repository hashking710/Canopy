import logging
from importlib.metadata import EntryPoint, entry_points

from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.adapters.mock import MockAdapter
from canopy_agent.models import Room

logger = logging.getLogger("canopy_agent.adapters.registry")

# Third-party adapter plugins register here, e.g. in a plugin's pyproject.toml:
#   [project.entry-points."canopy.sensor_adapters"]
#   my_device = "canopy_adapter_my_device:MyDeviceAdapter"
# See docs/plugin-development.md. "mock" is the only adapter this package ships
# itself — everything else is expected to arrive as a separately installed package.
PLUGIN_GROUP = "canopy.sensor_adapters"

_instances: dict[str, SensorAdapter] = {}
_factories: dict[str, type[SensorAdapter]] | None = None


def _load_factories() -> dict[str, type[SensorAdapter]]:
    global _factories
    if _factories is not None:
        return _factories

    factories: dict[str, type[SensorAdapter]] = {"mock": MockAdapter}
    for ep in entry_points(group=PLUGIN_GROUP):
        _register_plugin(factories, ep)
    _factories = factories
    return factories


def _register_plugin(factories: dict[str, type[SensorAdapter]], ep: EntryPoint) -> None:
    # A broken plugin (import error, wrong base class, whatever) must not take the
    # whole app down at startup — log it and keep going without that one adapter.
    # This is the whole point of a plugin ecosystem: a third party's bug is theirs.
    try:
        adapter_cls = ep.load()
    except Exception:
        logger.exception("failed to load sensor adapter plugin '%s' — skipping it", ep.name)
        return

    if not (isinstance(adapter_cls, type) and issubclass(adapter_cls, SensorAdapter)):
        logger.error(
            "sensor adapter plugin '%s' does not point at a SensorAdapter subclass — skipping it", ep.name
        )
        return

    if ep.name in factories:
        logger.warning("sensor adapter plugin '%s' conflicts with an existing adapter_type — skipping it", ep.name)
        return

    factories[ep.name] = adapter_cls


def available_adapter_types() -> dict[str, type[SensorAdapter]]:
    """adapter_type -> class, for anything that wants to list/describe what's installed."""
    return dict(_load_factories())


def get_adapter(room: Room) -> SensorAdapter:
    """
    One adapter instance per adapter_type, shared across every room that uses it —
    so e.g. all rooms on the same cloud account share one login session and one cached
    fetch, rather than each room re-authenticating separately.
    """
    adapter_type = room.adapter_type or "mock"
    if adapter_type not in _instances:
        factories = _load_factories()
        factory = factories.get(adapter_type)
        if factory is None:
            raise ValueError(
                f"unknown adapter_type '{adapter_type}' on room '{room.id}' "
                f"(installed: {sorted(factories)}) — is the plugin package installed?"
            )
        _instances[adapter_type] = factory()
    return _instances[adapter_type]
