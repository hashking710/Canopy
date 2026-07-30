import pytest

from canopy_agent.adapters import registry
from canopy_agent.adapters.base import SensorAdapter
from canopy_agent.adapters.mock import MockAdapter
from canopy_agent.adapters.registry import get_adapter
from canopy_agent.models import Room


class FakeEntryPoint:
    """Stands in for importlib.metadata.EntryPoint — same `.name`/`.load()` shape,
    but with a loader we control, so plugin-loading behavior is testable without
    actually installing a package."""

    def __init__(self, name, loader):
        self.name = name
        self._loader = loader

    def load(self):
        return self._loader()


class FakeAdapter(SensorAdapter):
    plugin_name = "Fake"

    async def connect(self, room):
        pass

    async def read(self, room):
        return {}

    async def disconnect(self, room):
        pass


class NotAnAdapter:
    pass


@pytest.fixture(autouse=True)
def reset_registry_state():
    # The registry caches discovered factories and instantiated adapters at module
    # scope (by design — one shared instance per adapter_type across rooms), which
    # would otherwise leak between tests.
    registry._factories = None
    registry._instances = {}
    yield
    registry._factories = None
    registry._instances = {}


def make_room(room_id: str = "r1", adapter_type: str = "mock", **kwargs) -> Room:
    return Room(id=room_id, room_type="greenhouse", path=f"~/{room_id}", adapter_type=adapter_type, metric_config={}, **kwargs)


def test_get_adapter_returns_mock_by_default():
    assert isinstance(get_adapter(make_room()), MockAdapter)


def test_get_adapter_shares_one_instance_across_rooms():
    room_a = make_room("room-a", "mock")
    room_b = make_room("room-b", "mock")
    assert get_adapter(room_a) is get_adapter(room_b)


def test_get_adapter_unknown_type_raises_and_lists_installed():
    with pytest.raises(ValueError, match="unknown adapter_type") as exc:
        get_adapter(make_room(adapter_type="not_a_real_adapter"))
    assert "mock" in str(exc.value)


def test_register_plugin_adds_valid_adapter():
    factories = {"mock": MockAdapter}
    registry._register_plugin(factories, FakeEntryPoint("fake", lambda: FakeAdapter))
    assert factories["fake"] is FakeAdapter


def test_register_plugin_skips_broken_loader_without_raising():
    def broken_loader():
        raise ImportError("simulated broken plugin package")

    factories = {"mock": MockAdapter}
    registry._register_plugin(factories, FakeEntryPoint("broken", broken_loader))
    assert "broken" not in factories


def test_register_plugin_skips_non_adapter_class():
    factories = {"mock": MockAdapter}
    registry._register_plugin(factories, FakeEntryPoint("not_an_adapter", lambda: NotAnAdapter))
    assert "not_an_adapter" not in factories


def test_register_plugin_skips_name_conflict():
    factories = {"mock": MockAdapter}
    registry._register_plugin(factories, FakeEntryPoint("mock", lambda: FakeAdapter))
    assert factories["mock"] is MockAdapter  # unchanged, not overwritten by the conflicting plugin


def test_available_adapter_types_includes_mock():
    assert "mock" in registry.available_adapter_types()
