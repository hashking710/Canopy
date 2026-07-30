import pytest

from canopy_agent.licensing import registry
from canopy_agent.licensing.base import LicenseGate
from canopy_agent.licensing.null_gate import AlwaysUnlockedGate
from canopy_agent.licensing.registry import get_license_gate


class FakeEntryPoint:
    """Same shape as tests/test_registry.py's — stands in for
    importlib.metadata.EntryPoint with a loader we control."""

    def __init__(self, name, loader):
        self.name = name
        self._loader = loader

    def load(self):
        return self._loader()


class FakeGate(LicenseGate):
    def is_feature_unlocked(self, feature: str) -> bool:
        return feature != "cross_device_relay"

    def status(self) -> dict:
        return {"tier": "corporate", "gate": "FakeGate"}


class BrokenGate(LicenseGate):
    def __init__(self):
        raise RuntimeError("simulated broken plugin constructor")

    def is_feature_unlocked(self, feature: str) -> bool:
        return True

    def status(self) -> dict:
        return {}


class NotAGate:
    pass


@pytest.fixture(autouse=True)
def reset_registry_state():
    registry._instance = None
    yield
    registry._instance = None


def test_defaults_to_always_unlocked_when_nothing_installed():
    gate = get_license_gate()
    assert isinstance(gate, AlwaysUnlockedGate)
    assert gate.is_feature_unlocked("cross_device_relay") is True


def test_caches_the_instance_across_calls():
    assert get_license_gate() is get_license_gate()


def test_try_load_accepts_a_valid_gate_plugin():
    gate = registry._try_load(FakeEntryPoint("fake", lambda: FakeGate))
    assert isinstance(gate, FakeGate)


def test_try_load_rejects_a_broken_loader():
    def broken_loader():
        raise ImportError("simulated broken plugin package")

    assert registry._try_load(FakeEntryPoint("broken", broken_loader)) is None


def test_try_load_rejects_a_non_license_gate_class():
    assert registry._try_load(FakeEntryPoint("not_a_gate", lambda: NotAGate)) is None


def test_try_load_rejects_a_gate_that_fails_to_construct():
    # A plugin that loads fine but blows up in __init__ must still fail open, not
    # crash the app — same "a broken plugin's bug stays theirs" philosophy as every
    # other plugin registry in this codebase.
    assert registry._try_load(FakeEntryPoint("broken_init", lambda: BrokenGate)) is None


def test_status_reports_unlicensed_by_default():
    status = get_license_gate().status()
    assert status["tier"] == "unlicensed"
