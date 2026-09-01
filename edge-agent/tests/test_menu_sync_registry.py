import pytest

from canopy_agent.menu_sync import registry
from canopy_agent.menu_sync.base import MenuSync
from canopy_agent.menu_sync.null_sync import NullMenuSync
from canopy_agent.menu_sync.registry import get_menu_sync


class FakeEntryPoint:
    def __init__(self, name, loader):
        self.name = name
        self._loader = loader

    def load(self):
        return self._loader()


class FakeMenuSync(MenuSync):
    plugin_name = "Fake"

    async def push_menu(self, items):
        return {"pushed": 0, "skipped": 0}


class NotAMenuSync:
    pass


@pytest.fixture(autouse=True)
def reset_registry_state():
    registry._factories = None
    registry._instance = None
    yield
    registry._factories = None
    registry._instance = None


def test_get_menu_sync_returns_null_by_default(monkeypatch):
    monkeypatch.delenv("CANOPY_MENU_SYNC", raising=False)
    assert isinstance(get_menu_sync(), NullMenuSync)


def test_get_menu_sync_caches_one_instance(monkeypatch):
    monkeypatch.delenv("CANOPY_MENU_SYNC", raising=False)
    assert get_menu_sync() is get_menu_sync()


def test_get_menu_sync_unknown_type_raises_and_lists_installed(monkeypatch):
    monkeypatch.setenv("CANOPY_MENU_SYNC", "not_a_real_provider")
    with pytest.raises(ValueError, match="unknown CANOPY_MENU_SYNC") as exc:
        get_menu_sync()
    assert "null" in str(exc.value)


def test_register_plugin_adds_valid_menu_sync():
    factories = {"null": NullMenuSync}
    registry._register_plugin(factories, FakeEntryPoint("fake", lambda: FakeMenuSync))
    assert factories["fake"] is FakeMenuSync


def test_register_plugin_skips_broken_loader_without_raising():
    def broken_loader():
        raise ImportError("simulated broken plugin package")

    factories = {"null": NullMenuSync}
    registry._register_plugin(factories, FakeEntryPoint("broken", broken_loader))
    assert "broken" not in factories


def test_register_plugin_skips_non_menu_sync_class():
    factories = {"null": NullMenuSync}
    registry._register_plugin(factories, FakeEntryPoint("not_a_menu_sync", lambda: NotAMenuSync))
    assert "not_a_menu_sync" not in factories


def test_register_plugin_skips_name_conflict():
    factories = {"null": NullMenuSync}
    registry._register_plugin(factories, FakeEntryPoint("null", lambda: FakeMenuSync))
    assert factories["null"] is NullMenuSync


def test_available_sync_types_includes_null():
    assert "null" in registry.available_sync_types()


async def test_null_menu_sync_reports_everything_skipped():
    result = await NullMenuSync().push_menu([{"item_name": "x"}])
    assert result == {"pushed": 0, "skipped": 1}
