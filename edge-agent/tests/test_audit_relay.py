from datetime import date, datetime, timezone

import canopy_agent.services.audit_relay as audit_relay
from canopy_agent.compliance_models import AuditLogEntry, Harvest, HarvestWeightLog, Package, Plant
from canopy_agent.models import Room
from canopy_agent.services.audit_relay import _get_cursor, process_relay_event


def make_room(db_session, room_id="local-room") -> Room:
    room = Room(id=room_id, room_type="greenhouse", path=f"~/{room_id}", metric_config={})
    db_session.add(room)
    db_session.commit()
    return room


def make_move_event(**overrides) -> dict:
    event = {
        "id": 1,
        "origin_device_id": "pi-a",
        "entity_type": "plant",
        "entity_id": "GMO-tag-001",
        "action": "moved",
        "actor": "Alex Rivera",
        "room_id": "remote-source-room",
        "details": {
            "from_room_id": "remote-source-room",
            "to_room_id": "local-room",
            "plant_snapshot": {
                "strain": "GMO",
                "growth_phase": "Flowering",
                "planted_date": "2026-06-01",
                "tagged_date": "2026-06-15",
                "mother_plant_id": None,
            },
        },
        "occurred_at": "2026-07-23T12:00:00",
        "entry_hash": "abc123",
    }
    event.update(overrides)
    return event


def test_ignores_its_own_echoed_event(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-a")
    make_room(db_session, "local-room")
    process_relay_event(db_session, make_move_event(origin_device_id="pi-a"))
    db_session.commit()
    assert db_session.get(Plant, "GMO-tag-001") is None


def test_ignores_non_moved_actions(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    make_room(db_session, "local-room")
    process_relay_event(db_session, make_move_event(action="destroyed"))
    db_session.commit()
    assert db_session.get(Plant, "GMO-tag-001") is None


def test_ignores_non_plant_entities(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    make_room(db_session, "local-room")
    process_relay_event(db_session, make_move_event(entity_type="harvest"))
    db_session.commit()
    assert db_session.get(Plant, "GMO-tag-001") is None


def test_ignores_moves_to_a_room_this_device_does_not_own(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    # Deliberately do NOT create "local-room" here — this device has no such room.
    process_relay_event(db_session, make_move_event())
    db_session.commit()
    assert db_session.get(Plant, "GMO-tag-001") is None


def test_creates_local_plant_from_a_genuine_cross_device_move(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    make_room(db_session, "local-room")

    process_relay_event(db_session, make_move_event())
    db_session.commit()

    plant = db_session.get(Plant, "GMO-tag-001")
    assert plant is not None
    assert plant.room_id == "local-room"
    assert plant.strain == "GMO"
    assert plant.growth_phase == "Flowering"
    assert plant.planted_date == date(2026, 6, 1)
    assert plant.tagged_date == date(2026, 6, 15)


def test_creates_a_local_audit_entry_with_origin_stitched_in(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    make_room(db_session, "local-room")

    process_relay_event(db_session, make_move_event())
    db_session.commit()

    entry = db_session.query(AuditLogEntry).filter_by(entity_id="GMO-tag-001").one()
    assert entry.action == "moved_in_from_relay"
    assert entry.origin_device_id == "pi-a"
    assert entry.origin_entry_hash == "abc123"
    assert entry.room_id == "local-room"


def test_processing_the_same_event_twice_is_a_no_op_the_second_time(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    make_room(db_session, "local-room")

    process_relay_event(db_session, make_move_event())
    process_relay_event(db_session, make_move_event())  # redelivery
    db_session.commit()

    assert db_session.query(Plant).filter_by(id="GMO-tag-001").count() == 1
    assert db_session.query(AuditLogEntry).filter_by(entity_id="GMO-tag-001").count() == 1


def make_harvest_created_event(**overrides) -> dict:
    event = {
        "id": 7,
        "origin_device_id": "pi-a",
        "entity_type": "harvest",
        "entity_id": "harvest-shared-001",
        "action": "created",
        "actor": "Alex Rivera",
        "room_id": "remote-source-room",
        "details": {
            "name": "GMO-2026-07-29",
            "strain": "GMO",
            "harvest_snapshot": {
                "name": "GMO-2026-07-29",
                "strain": "GMO",
                "source_room_id": "remote-source-room",
                "drying_room_id": None,
                "wet_weight_g": 0.0,
                "started_at": "2026-07-29T12:00:00+00:00",
            },
        },
        "occurred_at": "2026-07-29T12:00:00",
        "entry_hash": "harvesthash123",
    }
    event.update(overrides)
    return event


def test_ignores_its_own_echoed_harvest_created_event(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-a")
    process_relay_event(db_session, make_harvest_created_event(origin_device_id="pi-a"))
    db_session.commit()
    assert db_session.get(Harvest, "harvest-shared-001") is None


def test_syncs_a_harvest_created_on_a_different_device_regardless_of_room_ownership(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    # Deliberately no local room matching "remote-source-room" — unlike a plant move,
    # a harvest syncs everywhere at the site regardless of which device owns the
    # source room, since any device's plants should be harvestable into it.
    process_relay_event(db_session, make_harvest_created_event())
    db_session.commit()

    harvest = db_session.get(Harvest, "harvest-shared-001")
    assert harvest is not None
    assert harvest.name == "GMO-2026-07-29"
    assert harvest.strain == "GMO"
    assert harvest.source_room_id == "remote-source-room"
    assert harvest.drying_room_id is None
    assert harvest.wet_weight_g == 0.0
    assert harvest.started_at == datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc).replace(tzinfo=None)  # SQLite round-trips DateTime as naive
    assert harvest.status == "active"  # column default still applies


def test_harvest_sync_creates_a_local_audit_entry_with_origin_stitched_in(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    process_relay_event(db_session, make_harvest_created_event())
    db_session.commit()

    entry = db_session.query(AuditLogEntry).filter_by(entity_id="harvest-shared-001").one()
    assert entry.action == "harvest_synced_from_relay"
    assert entry.origin_device_id == "pi-a"
    assert entry.origin_entry_hash == "harvesthash123"


def test_harvest_sync_is_idempotent_on_redelivery(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    process_relay_event(db_session, make_harvest_created_event())
    process_relay_event(db_session, make_harvest_created_event())  # redelivery
    db_session.commit()

    assert db_session.query(Harvest).filter_by(id="harvest-shared-001").count() == 1
    assert db_session.query(AuditLogEntry).filter_by(entity_id="harvest-shared-001").count() == 1


def test_harvest_sync_is_skipped_without_a_snapshot(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    event = make_harvest_created_event()
    event["details"] = {"name": "GMO-2026-07-29", "strain": "GMO"}  # no harvest_snapshot key at all

    process_relay_event(db_session, event)
    db_session.commit()

    assert db_session.get(Harvest, "harvest-shared-001") is None


def make_synced_harvest(db_session, harvest_id="harvest-shared-001", wet_weight_g=0.0) -> Harvest:
    """A harvest already present locally, as if _process_harvest_created had already
    synced it here — the fixture every weigh/finish/package test below builds on."""
    harvest = Harvest(
        id=harvest_id, name=f"{harvest_id}-name", strain="GMO",
        source_room_id="remote-source-room", drying_room_id=None, wet_weight_g=wet_weight_g,
    )
    db_session.add(harvest)
    db_session.commit()
    return harvest


def make_plant_harvested_event(**overrides) -> dict:
    event = {
        "id": 10,
        "origin_device_id": "pi-a",
        "entity_type": "plant",
        "entity_id": "GMO-tag-001",
        "action": "harvested",
        "actor": "Alex Rivera",
        "room_id": "remote-source-room",
        "details": {"harvest_id": "harvest-shared-001", "weight_g": 50.0},
        "occurred_at": "2026-07-30T12:00:00",
        "entry_hash": "planthavvesthash",
    }
    event.update(overrides)
    return event


def test_plant_harvested_adds_a_wet_weight_log_and_updates_the_harvest_total(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    make_synced_harvest(db_session, wet_weight_g=100.0)

    process_relay_event(db_session, make_plant_harvested_event())
    db_session.commit()

    harvest = db_session.get(Harvest, "harvest-shared-001")
    assert harvest.wet_weight_g == 150.0
    log = db_session.query(HarvestWeightLog).filter_by(harvest_id="harvest-shared-001").one()
    assert log.stage == "wet"
    assert log.weight_g == 50.0


def test_plant_harvested_is_skipped_when_the_harvest_has_not_synced_here_yet(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    # deliberately no make_synced_harvest() call
    process_relay_event(db_session, make_plant_harvested_event())
    db_session.commit()
    assert db_session.query(HarvestWeightLog).count() == 0


def test_plant_harvested_is_idempotent_on_redelivery(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    make_synced_harvest(db_session, wet_weight_g=100.0)

    process_relay_event(db_session, make_plant_harvested_event())
    process_relay_event(db_session, make_plant_harvested_event())  # redelivery
    db_session.commit()

    assert db_session.get(Harvest, "harvest-shared-001").wet_weight_g == 150.0  # not 200
    assert db_session.query(HarvestWeightLog).count() == 1


def make_harvest_weighed_event(**overrides) -> dict:
    event = {
        "id": 11,
        "origin_device_id": "pi-a",
        "entity_type": "harvest",
        "entity_id": "harvest-shared-001",
        "action": "weighed",
        "actor": "Alex Rivera",
        "room_id": "remote-dry-room",
        "details": {"stage": "dry", "weight_g": 30.0},
        "occurred_at": "2026-07-31T12:00:00",
        "entry_hash": "harvestweighhash",
    }
    event.update(overrides)
    return event


def test_harvest_weighed_adds_a_weight_log_without_touching_wet_weight_g(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    make_synced_harvest(db_session, wet_weight_g=100.0)

    process_relay_event(db_session, make_harvest_weighed_event())
    db_session.commit()

    harvest = db_session.get(Harvest, "harvest-shared-001")
    assert harvest.wet_weight_g == 100.0  # weigh-ins other than the initial harvest don't add to this total
    log = db_session.query(HarvestWeightLog).filter_by(harvest_id="harvest-shared-001").one()
    assert log.stage == "dry"
    assert log.weight_g == 30.0
    assert log.room_id == "remote-dry-room"


def test_multiple_weigh_ins_for_the_same_harvest_all_apply_not_just_the_first(db_session, monkeypatch):
    # This is exactly why weigh-in idempotency can't be "does a weight log exist for
    # this harvest" — legitimately there are several, one per lifecycle stage.
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    make_synced_harvest(db_session)

    process_relay_event(db_session, make_harvest_weighed_event(id=11, entry_hash="hash-dry", details={"stage": "dry", "weight_g": 30.0}))
    process_relay_event(db_session, make_harvest_weighed_event(id=12, entry_hash="hash-cure", details={"stage": "cure", "weight_g": 25.0}))
    db_session.commit()

    stages = {log.stage: log.weight_g for log in db_session.query(HarvestWeightLog).filter_by(harvest_id="harvest-shared-001").all()}
    assert stages == {"dry": 30.0, "cure": 25.0}


def make_harvest_finished_event(**overrides) -> dict:
    event = {
        "id": 13,
        "origin_device_id": "pi-a",
        "entity_type": "harvest",
        "entity_id": "harvest-shared-001",
        "action": "finished",
        "actor": "Alex Rivera",
        "room_id": None,
        "details": {},
        "occurred_at": "2026-08-01T09:30:00",
        "entry_hash": "harvestfinishhash",
    }
    event.update(overrides)
    return event


def test_harvest_finished_marks_the_local_copy_finished_with_the_real_timestamp(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    make_synced_harvest(db_session)

    process_relay_event(db_session, make_harvest_finished_event())
    db_session.commit()

    harvest = db_session.get(Harvest, "harvest-shared-001")
    assert harvest.status == "finished"
    assert harvest.finished_at == datetime(2026, 8, 1, 9, 30)


def test_harvest_finished_is_idempotent_on_redelivery(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    make_synced_harvest(db_session)

    process_relay_event(db_session, make_harvest_finished_event())
    process_relay_event(db_session, make_harvest_finished_event())
    db_session.commit()

    entries = db_session.query(AuditLogEntry).filter_by(entity_id="harvest-shared-001", action="harvest_finish_synced_from_relay").all()
    assert len(entries) == 1


def make_package_created_event(**overrides) -> dict:
    event = {
        "id": 14,
        "origin_device_id": "pi-a",
        "entity_type": "package",
        "entity_id": "pkg-shared-001",
        "action": "created",
        "actor": "Alex Rivera",
        "room_id": "remote-dry-room",
        "details": {
            "harvest_id": "harvest-shared-001", "item_name": "GMO Trim", "weight_g": 200.0,
            "package_snapshot": {
                "harvest_id": "harvest-shared-001", "item_name": "GMO Trim", "weight_g": 200.0,
                "room_id": "remote-dry-room", "is_production_batch": False, "is_donation": False,
            },
        },
        "occurred_at": "2026-08-02T10:00:00",
        "entry_hash": "packagecreatedhash",
    }
    event.update(overrides)
    return event


def test_package_created_syncs_regardless_of_room_ownership(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    make_synced_harvest(db_session)

    process_relay_event(db_session, make_package_created_event())
    db_session.commit()

    package = db_session.get(Package, "pkg-shared-001")
    assert package is not None
    assert package.harvest_id == "harvest-shared-001"
    assert package.item_name == "GMO Trim"
    assert package.weight_g == 200.0
    assert package.room_id == "remote-dry-room"
    assert package.status == "active"  # column default still applies


def test_package_created_is_skipped_without_a_snapshot(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    event = make_package_created_event()
    event["details"] = {"harvest_id": "harvest-shared-001", "item_name": "GMO Trim", "weight_g": 200.0}

    process_relay_event(db_session, event)
    db_session.commit()

    assert db_session.get(Package, "pkg-shared-001") is None


def test_a_processed_derivative_package_is_not_relayed_yet(db_session, monkeypatch):
    # "processed" (the manufacturing-chain action) is a deliberately separate,
    # not-yet-handled case from "created" (a harvest-sourced package) — see
    # process_relay_event's docstring.
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    event = make_package_created_event(action="processed", entity_id="pkg-derivative-001")

    process_relay_event(db_session, event)
    db_session.commit()

    assert db_session.get(Package, "pkg-derivative-001") is None


def test_package_created_is_idempotent_on_redelivery(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    make_synced_harvest(db_session)

    process_relay_event(db_session, make_package_created_event())
    process_relay_event(db_session, make_package_created_event())
    db_session.commit()

    assert db_session.query(Package).filter_by(id="pkg-shared-001").count() == 1


def test_get_cursor_starts_at_zero_and_persists(db_session):
    cursor = _get_cursor(db_session, "publish")
    assert cursor.position == 0

    cursor.position = 42
    db_session.commit()

    reloaded = _get_cursor(db_session, "publish")
    assert reloaded.position == 42


async def test_publish_is_a_no_op_when_mqtt_is_not_configured(db_session, monkeypatch):
    monkeypatch.setattr(audit_relay.mqtt_publisher, "MQTT_HOST", None)
    from canopy_agent.services.audit import record_audit

    record_audit(db_session, "plant", "p1", "created", "Alex")
    db_session.commit()

    await audit_relay.publish_pending_audit_events(db_session)  # must not raise / must not touch the network
    cursor = _get_cursor(db_session, "publish")
    assert cursor.position == 0  # nothing was actually published, so the cursor shouldn't advance


async def test_publish_is_a_no_op_when_the_relay_feature_is_locked(db_session, monkeypatch):
    # MQTT IS configured here — this specifically proves the license gate is checked
    # independently of mqtt_enabled(), not that the whole function is a no-op for some
    # other reason.
    monkeypatch.setattr(audit_relay.mqtt_publisher, "MQTT_HOST", "localhost")
    from canopy_agent.services.audit import record_audit

    class LockedGate:
        def is_feature_unlocked(self, feature: str) -> bool:
            return False

    monkeypatch.setattr(audit_relay, "get_license_gate", lambda: LockedGate())

    record_audit(db_session, "plant", "p1", "created", "Alex")
    db_session.commit()

    await audit_relay.publish_pending_audit_events(db_session)
    cursor = _get_cursor(db_session, "publish")
    assert cursor.position == 0
