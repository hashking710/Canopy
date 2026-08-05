import logging
import os
from importlib.metadata import EntryPoint, entry_points

from canopy_agent.compliance_sync.base import ComplianceSync
from canopy_agent.compliance_sync.null_sync import NullComplianceSync

logger = logging.getLogger("canopy_agent.compliance_sync.registry")

# Same shape as adapters/registry.py, and for the same reason: a METRC/BioTrack/etc.
# sync target is exactly the "many possible, don't want to maintain them all"
# situation sensor adapters are. "null" is the only implementation this package ships
# itself; a real one arrives as a separately installed plugin package. Selected via
# CANOPY_COMPLIANCE_SYNC (defaults to "null" — no external reporting until configured).
PLUGIN_GROUP = "canopy.compliance_sync"

_instance: ComplianceSync | None = None
_factories: dict[str, type[ComplianceSync]] | None = None


def _load_factories() -> dict[str, type[ComplianceSync]]:
    global _factories
    if _factories is not None:
        return _factories

    factories: dict[str, type[ComplianceSync]] = {"null": NullComplianceSync}
    for ep in entry_points(group=PLUGIN_GROUP):
        _register_plugin(factories, ep)
    _factories = factories
    return factories


def _register_plugin(factories: dict[str, type[ComplianceSync]], ep: EntryPoint) -> None:
    try:
        sync_cls = ep.load()
    except Exception:
        logger.exception("failed to load compliance sync plugin '%s' — skipping it", ep.name)
        return

    if not (isinstance(sync_cls, type) and issubclass(sync_cls, ComplianceSync)):
        logger.error("compliance sync plugin '%s' does not point at a ComplianceSync subclass — skipping it", ep.name)
        return

    if ep.name in factories:
        logger.warning("compliance sync plugin '%s' conflicts with an existing sync type — skipping it", ep.name)
        return

    factories[ep.name] = sync_cls


def available_sync_types() -> dict[str, type[ComplianceSync]]:
    """sync_type -> class, for anything that wants to list/describe what's
    installed (mirrors adapters.registry.available_adapter_types)."""
    return dict(_load_factories())


def get_compliance_sync() -> ComplianceSync:
    global _instance
    if _instance is None:
        sync_type = os.environ.get("CANOPY_COMPLIANCE_SYNC", "null")
        factories = _load_factories()
        factory = factories.get(sync_type)
        if factory is None:
            raise ValueError(
                f"unknown CANOPY_COMPLIANCE_SYNC '{sync_type}' (installed: {sorted(factories)}) — "
                "is the plugin package installed?"
            )
        _instance = factory()
    return _instance
