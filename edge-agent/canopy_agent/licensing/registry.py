import logging
from importlib.metadata import EntryPoint, entry_points

from canopy_agent.licensing.base import LicenseGate
from canopy_agent.licensing.null_gate import AlwaysUnlockedGate

logger = logging.getLogger("canopy_agent.licensing.registry")

# A separately installed, closed-source `canopy-license` package registers here — see
# docs/licensing-design.md. Unlike adapters/compliance_sync/notifications, there's no
# selection to make: at most one real gate is ever expected to be installed, so this
# just uses whatever's found, falling back to AlwaysUnlockedGate if nothing is (or if
# what's installed is broken — a bug in a license-check plugin must fail toward every
# feature staying unlocked, never toward bricking a customer's compliance tracking,
# same philosophy as every other plugin gate in this codebase failing safe rather than
# taking the app down).
PLUGIN_GROUP = "canopy.license_gate"

_instance: LicenseGate | None = None


def get_license_gate() -> LicenseGate:
    global _instance
    if _instance is not None:
        return _instance

    for ep in entry_points(group=PLUGIN_GROUP):
        gate = _try_load(ep)
        if gate is not None:
            _instance = gate
            return _instance

    _instance = AlwaysUnlockedGate()
    return _instance


def _try_load(ep: EntryPoint) -> LicenseGate | None:
    try:
        gate_cls = ep.load()
    except Exception:
        logger.exception("failed to load license gate plugin '%s' — falling back to unlocked", ep.name)
        return None

    if not (isinstance(gate_cls, type) and issubclass(gate_cls, LicenseGate)):
        logger.error("license gate plugin '%s' does not point at a LicenseGate subclass — falling back to unlocked", ep.name)
        return None

    try:
        return gate_cls()
    except Exception:
        logger.exception("failed to instantiate license gate plugin '%s' — falling back to unlocked", ep.name)
        return None
