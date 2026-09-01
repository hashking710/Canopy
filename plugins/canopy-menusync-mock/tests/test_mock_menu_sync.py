from canopy_menusync_mock import MockMenuSync


def make_item(**overrides):
    item = {
        "package_id": "pkg-1",
        "item_name": "GMO Flower",
        "weight_g": 453.6,
        "price_cents": 4500,
        "room_id": "vault",
        "strain_name": "GMO",
        "strain_type": "hybrid",
        "lineage": "Chemdog x Girl Scout Cookies",
        "thc_pct": 24.5,
        "cbd_pct": 0.3,
    }
    item.update(overrides)
    return item


async def test_push_menu_records_and_reports_pushed_count():
    sync = MockMenuSync()
    result = await sync.push_menu([make_item(), make_item(package_id="pkg-2")])

    assert result == {"pushed": 2, "skipped": 0}
    assert len(sync.pushes) == 1
    assert len(sync.pushes[0]) == 2


async def test_push_menu_with_no_items():
    sync = MockMenuSync()
    result = await sync.push_menu([])
    assert result == {"pushed": 0, "skipped": 0}


async def test_pushes_accumulate_across_calls():
    sync = MockMenuSync()
    await sync.push_menu([make_item()])
    await sync.push_menu([make_item(), make_item(package_id="pkg-2")])
    assert len(sync.pushes) == 2


def test_plugin_metadata_is_set():
    assert MockMenuSync.plugin_name == "Mock POS/Menu (testing)"
    assert MockMenuSync.required_env_vars == {}
