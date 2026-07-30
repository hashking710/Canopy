import pytest

from canopy_agent.adapters.mock import MockAdapter
from canopy_agent.models import Room


def make_room(metric_config: dict) -> Room:
    return Room(id="r1", room_type="greenhouse", path="r1", adapter_type="mock", metric_config=metric_config)


async def test_read_walks_within_the_configured_range():
    adapter = MockAdapter()
    room = make_room({"temp_f": {"label": "temp", "min": 70, "max": 80}})
    values = await adapter.read(room)
    assert 70 <= values["temp_f"] <= 80


async def test_missing_min_max_raises_a_clear_error_not_a_bare_keyerror():
    adapter = MockAdapter()
    room = make_room({"temp_f": {"label": "temp"}})
    with pytest.raises(RuntimeError, match="missing 'min'/'max'"):
        await adapter.read(room)


async def test_derived_metrics_are_skipped_without_needing_min_max():
    adapter = MockAdapter()
    room = make_room({"vpd_kpa": {"label": "VPD", "derived": "vpd"}})
    values = await adapter.read(room)
    assert values == {}


async def test_successive_reads_stay_bounded_and_drift():
    adapter = MockAdapter()
    room = make_room({"temp_f": {"label": "temp", "min": 70, "max": 80, "step": 5}})
    seen = set()
    for _ in range(20):
        values = await adapter.read(room)
        assert 70 <= values["temp_f"] <= 80
        seen.add(round(values["temp_f"], 3))
    assert len(seen) > 1  # it's actually walking, not stuck at one value
