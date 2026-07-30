from canopy_master import store as store_module
from canopy_master.store import ONLINE_THRESHOLD_SECONDS, Store


def test_upsert_and_site_summaries():
    s = Store()
    s.upsert_room("site-1", "facility", {"id": "facility"})
    s.upsert_room("site-1", "greenhouse-a", {"id": "greenhouse-a"})
    s.upsert_room("site-2", "facility", {"id": "facility"})

    summaries = {row["site_id"]: row for row in s.site_summaries()}
    assert summaries["site-1"]["room_count"] == 2
    assert summaries["site-2"]["room_count"] == 1
    assert summaries["site-1"]["online"] is True


def test_site_goes_offline_after_threshold(monkeypatch):
    s = Store()
    clock = {"now": 1000.0}
    monkeypatch.setattr(store_module.time, "monotonic", lambda: clock["now"])

    s.upsert_room("site-1", "facility", {"id": "facility"})
    assert s.site_summaries()[0]["online"] is True

    clock["now"] += ONLINE_THRESHOLD_SECONDS + 1
    assert s.site_summaries()[0]["online"] is False


def test_upsert_overwrites_previous_payload_for_same_room():
    s = Store()
    s.upsert_room("site-1", "greenhouse-a", {"id": "greenhouse-a", "stats": [{"value": 1}]})
    s.upsert_room("site-1", "greenhouse-a", {"id": "greenhouse-a", "stats": [{"value": 2}]})

    rooms = s.rooms_for_site("site-1")
    assert len(rooms) == 1
    assert rooms[0]["stats"][0]["value"] == 2


def test_rooms_for_unknown_site_is_empty():
    s = Store()
    assert s.rooms_for_site("no-such-site") == []
