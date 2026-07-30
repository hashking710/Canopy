from canopy_master.audit_store import list_relayed_events, record_relayed_event


def _payload(**overrides):
    base = {
        "id": 1,
        "origin_device_id": "pi-veg",
        "entity_type": "plant",
        "entity_id": "plant-abc",
        "action": "moved",
        "actor": "Alex Rivera",
        "room_id": "greenhouse-a",
        "details": {"to_room_id": "greenhouse-a"},
        "occurred_at": "2026-07-29T12:00:00+00:00",
        "entry_hash": "deadbeef",
    }
    base.update(overrides)
    return base


def test_recording_a_new_event_returns_true_and_persists_it(db_session):
    created = record_relayed_event(db_session, "site-1", _payload())
    assert created is True

    events = list_relayed_events(db_session)
    assert len(events) == 1
    assert events[0].site_id == "site-1"
    assert events[0].origin_device_id == "pi-veg"
    assert events[0].origin_entry_id == 1
    assert events[0].actor == "Alex Rivera"
    assert events[0].details == {"to_room_id": "greenhouse-a"}


def test_recording_the_same_event_twice_is_idempotent(db_session):
    first = record_relayed_event(db_session, "site-1", _payload())
    second = record_relayed_event(db_session, "site-1", _payload())
    assert first is True
    assert second is False
    assert len(list_relayed_events(db_session)) == 1


def test_same_origin_entry_id_from_different_devices_or_sites_are_distinct(db_session):
    # id=1 is only unique WITHIN one device's own chain — the same integer will recur
    # on every other device and every other site, so the triple (site, device, id) is
    # what actually has to be the dedup key, not id alone.
    record_relayed_event(db_session, "site-1", _payload(id=1, origin_device_id="pi-veg"))
    record_relayed_event(db_session, "site-1", _payload(id=1, origin_device_id="pi-flower"))
    record_relayed_event(db_session, "site-2", _payload(id=1, origin_device_id="pi-veg"))

    assert len(list_relayed_events(db_session)) == 3


def test_list_can_filter_to_one_site(db_session):
    record_relayed_event(db_session, "site-1", _payload(id=1))
    record_relayed_event(db_session, "site-2", _payload(id=2))

    only_site_1 = list_relayed_events(db_session, site_id="site-1")
    assert len(only_site_1) == 1
    assert only_site_1[0].site_id == "site-1"


def test_list_respects_limit(db_session):
    for i in range(5):
        record_relayed_event(db_session, "site-1", _payload(id=i, occurred_at=f"2026-07-2{i}T00:00:00+00:00"))

    assert len(list_relayed_events(db_session, limit=2)) == 2
