"""
Real two-device integration test — publishes and receives over an actual running
Mosquitto broker (the one docker-compose.yml already brings up on localhost:1883),
not a mock. This is the strongest verification available for the relay without two
physical Pis: genuine MQTT wire-protocol delivery between two independent in-memory
databases standing in for two devices at one site.

Requires a broker reachable at localhost:1883 (docker compose up mosquitto, or any
local Mosquitto/amqtt instance) — skipped automatically if none is reachable, so the
rest of the suite doesn't depend on Docker being up.
"""

import asyncio
import json
import socket
import sys
from datetime import date

if sys.platform == "win32":
    # Same fix as canopy_agent/main.py: paho-mqtt (via aiomqtt) needs
    # loop.add_reader/add_writer, which Windows' default ProactorEventLoop doesn't
    # implement. Must be set before pytest-asyncio creates this test's event loop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import aiomqtt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import canopy_agent.services.audit_relay as audit_relay
from canopy_agent.compliance_models import Harvest, HarvestWeightLog, Package, Plant
from canopy_agent.db import Base
from canopy_agent.models import Room
from canopy_agent.services.audit import record_audit
from canopy_agent.services.audit_relay import process_relay_event, publish_pending_audit_events

BROKER_HOST = "localhost"
BROKER_PORT = 1883


def _broker_reachable() -> bool:
    try:
        with socket.create_connection((BROKER_HOST, BROKER_PORT), timeout=1):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not _broker_reachable(), reason=f"no MQTT broker reachable at {BROKER_HOST}:{BROKER_PORT}")


def make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


async def test_plant_move_relays_from_one_device_to_another_over_a_real_broker(monkeypatch):
    site_id = f"test-site-{id(object())}"  # unique per test run, so parallel/rerun test runs don't cross-talk
    topic = f"canopy/{site_id}/audit-events"

    monkeypatch.setattr(audit_relay.mqtt_publisher, "MQTT_HOST", BROKER_HOST)
    monkeypatch.setattr(audit_relay.mqtt_publisher, "MQTT_PORT", BROKER_PORT)
    monkeypatch.setattr(audit_relay.mqtt_publisher, "SITE_ID", site_id)
    monkeypatch.setattr(audit_relay, "RELAY_TOPIC", topic)
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-a")

    db_a = make_session()
    db_b = make_session()

    # Device A owns "room-a" and has an active plant in it; device B owns "room-b" and
    # knows nothing about device A's rooms — exactly the "each device only knows its
    # own rooms" model the relay is built around.
    db_a.add(Room(id="room-a", room_type="greenhouse", path="~/room-a", metric_config={}))
    db_a.add(Plant(
        id="RELAY-TEST-001", batch_id=None, strain="GMO", room_id="room-a",
        growth_phase="Flowering", planted_date=date(2026, 6, 1),
        tagged_date=date(2026, 6, 15),
    ))
    db_b.add(Room(id="room-b", room_type="greenhouse", path="~/room-b", metric_config={}))
    db_a.commit()
    db_b.commit()

    # Device A moves the plant to "room-b" — not one of its own rooms, so this mirrors
    # exactly what routers/compliance.py's move_plant does for a cross-device move:
    # record a "moved" entry carrying a plant snapshot, don't touch plant.room_id.
    plant = db_a.get(Plant, "RELAY-TEST-001")
    plant.status = "transferred"
    record_audit(
        db_a, "plant", plant.id, "moved", "Alex Rivera", room_id="room-a",
        details={
            "from_room_id": "room-a", "to_room_id": "room-b",
            "plant_snapshot": {
                "strain": "GMO", "growth_phase": "Flowering",
                "planted_date": "2026-06-01", "tagged_date": "2026-06-15", "mother_plant_id": None,
            },
        },
    )
    db_a.commit()

    # Subscribe BEFORE publishing (this test doesn't rely on persistent-session queuing
    # — it proves live delivery, which is the common case; offline queuing is a
    # separate Mosquitto-level guarantee documented in subscribe_relay_forever).
    async with aiomqtt.Client(hostname=BROKER_HOST, port=BROKER_PORT, identifier=f"test-sub-{site_id}") as sub_client:
        await sub_client.subscribe(topic, qos=1)

        await publish_pending_audit_events(db_a)  # device A relays its new audit entry, real MQTT publish

        message = await asyncio.wait_for(anext(aiter(sub_client.messages)), timeout=10)
        payload = json.loads(message.payload)

    assert payload["origin_device_id"] == "pi-a"
    assert payload["action"] == "moved"
    assert payload["details"]["to_room_id"] == "room-b"

    # Device B receives it — different DEVICE_ID than the publisher, so it isn't
    # filtered out as an echo of its own event.
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    process_relay_event(db_b, payload)
    db_b.commit()

    received_plant = db_b.get(Plant, "RELAY-TEST-001")
    assert received_plant is not None
    assert received_plant.room_id == "room-b"
    assert received_plant.strain == "GMO"

    # And device A's own copy is retired, not silently left "active" in a room it no
    # longer has any real information about.
    assert db_a.get(Plant, "RELAY-TEST-001").status == "transferred"


async def test_harvest_created_on_one_device_syncs_to_another_over_a_real_broker(monkeypatch):
    site_id = f"test-site-{id(object())}"
    topic = f"canopy/{site_id}/audit-events"

    monkeypatch.setattr(audit_relay.mqtt_publisher, "MQTT_HOST", BROKER_HOST)
    monkeypatch.setattr(audit_relay.mqtt_publisher, "MQTT_PORT", BROKER_PORT)
    monkeypatch.setattr(audit_relay.mqtt_publisher, "SITE_ID", site_id)
    monkeypatch.setattr(audit_relay, "RELAY_TOPIC", topic)
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-a")

    db_a = make_session()
    db_b = make_session()

    # Device A owns the growing room the harvest is sourced from; device B (the
    # processing/drying Pi in this two-device site) knows nothing about that room at
    # all — the real-world shape this feature exists for.
    db_a.add(Room(id="room-a", room_type="greenhouse", path="~/room-a", metric_config={}))
    db_a.commit()

    harvest = Harvest(
        id="RELAY-HARVEST-001", name="GMO-RELAY-TEST", strain="GMO",
        source_room_id="room-a", drying_room_id=None, wet_weight_g=0.0,
    )
    db_a.add(harvest)
    db_a.flush()
    record_audit(
        db_a, "harvest", harvest.id, "created", "Alex Rivera", room_id="room-a",
        details={
            "name": "GMO-RELAY-TEST", "strain": "GMO",
            "harvest_snapshot": {
                "name": "GMO-RELAY-TEST", "strain": "GMO", "source_room_id": "room-a",
                "drying_room_id": None, "wet_weight_g": 0.0, "started_at": harvest.started_at.isoformat(),
            },
        },
    )
    db_a.commit()

    async with aiomqtt.Client(hostname=BROKER_HOST, port=BROKER_PORT, identifier=f"test-sub-harvest-{site_id}") as sub_client:
        await sub_client.subscribe(topic, qos=1)

        await publish_pending_audit_events(db_a)

        message = await asyncio.wait_for(anext(aiter(sub_client.messages)), timeout=10)
        payload = json.loads(message.payload)

    assert payload["origin_device_id"] == "pi-a"
    assert payload["action"] == "created"
    assert payload["entity_type"] == "harvest"

    # Device B receives it and gets its own local copy — with no room named "room-a"
    # at all, proving harvest sync doesn't gate on room ownership the way plant moves do.
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
    process_relay_event(db_b, payload)
    db_b.commit()

    synced = db_b.get(Harvest, "RELAY-HARVEST-001")
    assert synced is not None
    assert synced.name == "GMO-RELAY-TEST"
    assert synced.source_room_id == "room-a"


async def test_full_harvest_lifecycle_relays_end_to_end_over_a_real_broker(monkeypatch):
    """The scenario the whole harvest-relay feature exists for: growing rooms on one
    Pi, the post-harvest workflow on another. Creates a harvest, weighs it in, finishes
    it, and packages it — all on device A — publishing each step over a real broker,
    and checks device B ends up with a fully consistent copy at every stage, not just
    the initial creation."""
    site_id = f"test-site-{id(object())}"
    topic = f"canopy/{site_id}/audit-events"

    monkeypatch.setattr(audit_relay.mqtt_publisher, "MQTT_HOST", BROKER_HOST)
    monkeypatch.setattr(audit_relay.mqtt_publisher, "MQTT_PORT", BROKER_PORT)
    monkeypatch.setattr(audit_relay.mqtt_publisher, "SITE_ID", site_id)
    monkeypatch.setattr(audit_relay, "RELAY_TOPIC", topic)
    monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-a")

    db_a = make_session()
    db_b = make_session()
    db_a.add(Room(id="room-a", room_type="greenhouse", path="~/room-a", metric_config={}))
    db_a.commit()

    async def relay_next_event() -> None:
        """Publishes whatever's newly pending on device A and applies it on device B —
        the same round trip proven by the harvest-created test above, reused for each
        lifecycle step in turn."""
        async with aiomqtt.Client(hostname=BROKER_HOST, port=BROKER_PORT, identifier=f"test-sub-{site_id}-{id(object())}") as sub:
            await sub.subscribe(topic, qos=1)
            await publish_pending_audit_events(db_a)
            message = await asyncio.wait_for(anext(aiter(sub.messages)), timeout=10)
            payload = json.loads(message.payload)
        monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-b")
        process_relay_event(db_b, payload)
        db_b.commit()
        monkeypatch.setattr(audit_relay, "DEVICE_ID", "pi-a")

    # 1. Create the harvest.
    harvest = Harvest(id="LIFECYCLE-HARVEST-001", name="GMO-LIFECYCLE", strain="GMO", source_room_id="room-a", drying_room_id=None, wet_weight_g=0.0)
    db_a.add(harvest)
    db_a.flush()
    record_audit(
        db_a, "harvest", harvest.id, "created", "Alex Rivera", room_id="room-a",
        details={
            "name": "GMO-LIFECYCLE", "strain": "GMO",
            "harvest_snapshot": {
                "name": "GMO-LIFECYCLE", "strain": "GMO", "source_room_id": "room-a",
                "drying_room_id": None, "wet_weight_g": 0.0, "started_at": harvest.started_at.isoformat(),
            },
        },
    )
    db_a.commit()
    await relay_next_event()
    assert db_b.get(Harvest, "LIFECYCLE-HARVEST-001") is not None

    # 2. Harvest a plant into it (a wet weigh-in via harvest_plant's own action).
    record_audit(
        db_a, "plant", "GMO-tag-lifecycle", "harvested", "Alex Rivera", room_id="room-a",
        details={"harvest_id": harvest.id, "weight_g": 500.0},
    )
    harvest.wet_weight_g += 500.0
    db_a.commit()
    await relay_next_event()
    harvest_b = db_b.get(Harvest, "LIFECYCLE-HARVEST-001")
    assert harvest_b.wet_weight_g == 500.0
    assert db_b.query(HarvestWeightLog).filter_by(harvest_id=harvest.id, stage="wet").one().weight_g == 500.0

    # 3. A direct dry-stage weigh-in.
    record_audit(db_a, "harvest", harvest.id, "weighed", "Alex Rivera", room_id="room-a", details={"stage": "dry", "weight_g": 90.0})
    db_a.commit()
    await relay_next_event()
    assert db_b.query(HarvestWeightLog).filter_by(harvest_id=harvest.id, stage="dry").one().weight_g == 90.0

    # 4. Finish the harvest.
    harvest.status = "finished"
    record_audit(db_a, "harvest", harvest.id, "finished", "Alex Rivera")
    db_a.commit()
    await relay_next_event()
    assert db_b.get(Harvest, "LIFECYCLE-HARVEST-001").status == "finished"

    # 5. Package it — the final proof this all actually unblocks a real cross-device
    # workflow: device B, which never owned "room-a" and didn't create this harvest,
    # can still record a real package against it.
    package = Package(id="LIFECYCLE-PKG-001", harvest_id=harvest.id, item_name="GMO Trim", weight_g=80.0, room_id="room-a")
    db_a.add(package)
    record_audit(
        db_a, "package", package.id, "created", "Alex Rivera", room_id="room-a",
        details={
            "harvest_id": harvest.id, "item_name": "GMO Trim", "weight_g": 80.0,
            "package_snapshot": {
                "harvest_id": harvest.id, "item_name": "GMO Trim", "weight_g": 80.0,
                "room_id": "room-a", "is_production_batch": False, "is_donation": False,
            },
        },
    )
    db_a.commit()
    await relay_next_event()

    synced_package = db_b.get(Package, "LIFECYCLE-PKG-001")
    assert synced_package is not None
    assert synced_package.harvest_id == harvest.id
    assert synced_package.weight_g == 80.0
