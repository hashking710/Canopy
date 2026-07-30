import asyncio
import json
import logging
import os
from datetime import date, datetime

import aiomqtt
from sqlalchemy import select
from sqlalchemy.orm import Session

from canopy_agent.compliance_models import AuditLogEntry, Harvest, HarvestWeightLog, Package, Plant, RelayCursor, utcnow
from canopy_agent.db import SessionLocal
from canopy_agent.licensing.registry import get_license_gate
from canopy_agent.models import Room
from canopy_agent.services import mqtt_publisher
from canopy_agent.services.audit import record_audit

logger = logging.getLogger("canopy_agent.audit_relay")

# Defaults to SITE_ID so a single-device site (today's only real deployment shape)
# needs zero new configuration — DEVICE_ID only has to be set explicitly once a second
# Pi joins the same site.
DEVICE_ID = os.environ.get("CANOPY_DEVICE_ID", mqtt_publisher.SITE_ID)

RELAY_TOPIC = f"canopy/{mqtt_publisher.SITE_ID}/audit-events"
RECONNECT_DELAY_SECONDS = 5

# See docs/licensing-design.md — the cross-device relay is the corporate-tier feature.
# With no canopy-license package installed, get_license_gate() returns
# AlwaysUnlockedGate and this is always True, so the relay behaves exactly as it did
# before licensing existed for every deployment that hasn't opted into gating at all.
LICENSE_FEATURE = "cross_device_relay"


def _get_cursor(db: Session, name: str) -> RelayCursor:
    cursor = db.get(RelayCursor, name)
    if cursor is None:
        cursor = RelayCursor(name=name, position=0)
        db.add(cursor)
        db.flush()
    return cursor


def _entry_to_payload(entry: AuditLogEntry) -> dict:
    return {
        "id": entry.id,
        "origin_device_id": DEVICE_ID,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "action": entry.action,
        "actor": entry.actor,
        "room_id": entry.room_id,
        "details": entry.details,
        "occurred_at": entry.occurred_at.isoformat(),
        "entry_hash": entry.entry_hash,
    }


async def publish_pending_audit_events(db: Session) -> None:
    """
    Called once per poll cycle (see poller.py), same cadence as room-state publishing.
    Batches every locally-created AuditLogEntry this device hasn't relayed yet and
    publishes each individually, QoS 1, NOT retained — every entry matters and none
    should be silently overwritten by a later one the way retained room-state readings
    are. Entirely optional and non-blocking: if CANOPY_MQTT_HOST isn't set or the
    broker is unreachable, this must never affect local operation, matching
    mqtt_publisher.publish_states.
    """
    if not mqtt_publisher.mqtt_enabled():
        return
    if not get_license_gate().is_feature_unlocked(LICENSE_FEATURE):
        return

    cursor = _get_cursor(db, "publish")
    pending = db.execute(
        select(AuditLogEntry).where(AuditLogEntry.id > cursor.position).order_by(AuditLogEntry.id)
    ).scalars().all()
    if not pending:
        return

    try:
        async with aiomqtt.Client(
            hostname=mqtt_publisher.MQTT_HOST, port=mqtt_publisher.MQTT_PORT,
            identifier=f"canopy-{mqtt_publisher.SITE_ID}-{DEVICE_ID}-relay-publish",
            **mqtt_publisher.mqtt_connect_kwargs(),
        ) as client:
            for entry in pending:
                payload = json.dumps(_entry_to_payload(entry), default=_json_default)
                await client.publish(RELAY_TOPIC, payload=payload, qos=1, retain=False)
                cursor.position = entry.id
        db.commit()
    except Exception:
        logger.warning("audit relay publish failed this cycle; will retry next cycle", exc_info=True)
        db.rollback()


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"not JSON serializable: {value!r}")


async def subscribe_relay_forever() -> None:
    """
    Long-lived subscriber to this site's audit-event relay topic — every device at a
    site (including this one) publishes here; this is how a plant move onto one of
    THIS device's rooms, initiated on a different device, actually arrives. Uses a
    stable client identifier + clean_session=False so Mosquitto queues messages for
    this device while it's briefly offline, rather than only delivering what's
    published while connected — standard MQTT persistent-session behavior, not custom
    retry logic. A brand-new device (never connected with this identifier before) only
    sees events from the point it first connects onward, which is the correct behavior:
    it doesn't need to replay a site's entire history, just moves happening from here on.
    """
    if not mqtt_publisher.mqtt_enabled():
        return
    while True:
        if not get_license_gate().is_feature_unlocked(LICENSE_FEATURE):
            # Re-checked here rather than only once at startup, so a license that
            # unlocks (or degrades — see the 30-day grace period in
            # docs/licensing-design.md) takes effect on the next reconnect rather than
            # requiring a process restart. A live connection isn't torn down mid-flight
            # just because a check-in landed differently — resolution granularity is
            # "next reconnect," which happens periodically anyway from ordinary network
            # blips, and that's adequate given how generous the grace period is.
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)
            continue
        try:
            async with aiomqtt.Client(
                hostname=mqtt_publisher.MQTT_HOST, port=mqtt_publisher.MQTT_PORT,
                identifier=f"canopy-{mqtt_publisher.SITE_ID}-{DEVICE_ID}-relay-subscribe",
                clean_session=False,
                **mqtt_publisher.mqtt_connect_kwargs(),
            ) as client:
                await client.subscribe(RELAY_TOPIC, qos=1)
                logger.info("subscribed to %s as device '%s'", RELAY_TOPIC, DEVICE_ID)
                async for message in client.messages:
                    _handle_relay_message(message)
        except Exception:
            logger.warning(
                "audit relay subscribe connection lost; retrying in %ss", RECONNECT_DELAY_SECONDS, exc_info=True
            )
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)


def _handle_relay_message(message: aiomqtt.Message) -> None:
    db = SessionLocal()
    try:
        try:
            payload = json.loads(message.payload)
        except Exception:
            logger.warning("ignoring malformed relay message on %s", message.topic)
            return
        process_relay_event(db, payload)
        db.commit()
    except Exception:
        logger.exception("failed to process relay event: %s", message.payload)
        db.rollback()
    finally:
        db.close()


def process_relay_event(db: Session, event: dict) -> None:
    """
    The actual cross-device logic, split out from message handling so it's directly
    unit-testable without a real MQTT round-trip. Handles the full harvest lifecycle,
    not just its creation, so a harvest recorded on one device stays correct and
    finishable/packageable from any device at the site:

    - plant "moved" onto one of THIS device's rooms (_process_plant_moved)
    - harvest "created" anywhere at the site (_process_harvest_created)
    - plant "harvested" (into a wet-weight log on the harvest) (_process_plant_harvested)
    - harvest "weighed" (a wet/dry/cure checkpoint) (_process_harvest_weighed)
    - harvest "finished" (_process_harvest_finished)
    - package "created" from a harvest (_process_package_created)

    Not relayed: a package "processed" into a manufacturing derivative (BHO/CO2/
    distillation chains) — a genuinely separate, not-yet-tackled piece; see
    docs/architecture.md.

    Everything else (this device's own echoed-back events, plant moves onto some
    other device's rooms, any other action/entity_type) is silently ignored, since
    every device at a site sees every event on the shared topic and must filter for
    what applies to it locally; nothing centrally tracks room ownership.
    """
    if event.get("origin_device_id") == DEVICE_ID:
        return  # our own event, echoed back by the broker

    action, entity_type = event.get("action"), event.get("entity_type")
    if action == "moved" and entity_type == "plant":
        _process_plant_moved(db, event)
    elif action == "created" and entity_type == "harvest":
        _process_harvest_created(db, event)
    elif action == "harvested" and entity_type == "plant":
        _process_plant_harvested(db, event)
    elif action == "weighed" and entity_type == "harvest":
        _process_harvest_weighed(db, event)
    elif action == "finished" and entity_type == "harvest":
        _process_harvest_finished(db, event)
    elif action == "created" and entity_type == "package":
        _process_package_created(db, event)


def _already_relayed(db: Session, event: dict) -> bool:
    """Idempotency via the local audit trail's origin_entry_hash, rather than
    checking whether some entity already exists — needed for handlers below whose
    action can legitimately recur against the same entity_id (e.g. several weigh-ins
    against one harvest over its wet/dry/cure lifecycle), where "does the entity
    exist" can't tell redelivery apart from a second, genuinely new event."""
    entry_hash = event.get("entry_hash")
    if not entry_hash:
        return False
    return db.execute(select(AuditLogEntry.id).where(AuditLogEntry.origin_entry_hash == entry_hash)).first() is not None


def _record_relay_receipt(db: Session, entity_type: str, entity_id: str, action: str, event: dict, room_id: str | None) -> None:
    """Common tail end for every relay handler below: a local audit entry noting
    where this came from, hash-chained into *this* device's own chain as normal (see
    docs/architecture.md's "stitched chains, not one global chain")."""
    record_audit(
        db, entity_type, entity_id, action, event.get("actor", "unknown"), room_id=room_id,
        details={"origin_device_id": event["origin_device_id"], "origin_room_id": event.get("room_id")},
    )
    # Set the origin reference on the entry record_audit just created — a small direct
    # update rather than threading two new optional kwargs through record_audit's
    # signature for every other caller that will never use them.
    new_entry = db.execute(
        select(AuditLogEntry).where(AuditLogEntry.entity_id == entity_id, AuditLogEntry.action == action)
        .order_by(AuditLogEntry.id.desc()).limit(1)
    ).scalar_one()
    new_entry.origin_device_id = event["origin_device_id"]
    new_entry.origin_entry_hash = event.get("entry_hash")
    # Flushed (not committed — that stays the caller's call) so _already_relayed's
    # origin_entry_hash lookup sees this immediately, including within a single
    # uncommitted session processing several events back-to-back (as tests do; real
    # usage commits after every message anyway, see _handle_relay_message).
    db.flush()


def _process_plant_moved(db: Session, event: dict) -> None:
    to_room_id = (event.get("details") or {}).get("to_room_id")
    if not to_room_id or db.get(Room, to_room_id) is None:
        return  # not one of our rooms

    plant_id = event["entity_id"]
    if db.get(Plant, plant_id) is not None:
        return  # already processed — redelivery must be a no-op, not a duplicate plant

    details = event.get("details") or {}
    snapshot = details.get("plant_snapshot") or {}
    plant = Plant(
        id=plant_id,
        batch_id=None,
        strain=snapshot.get("strain", "unknown"),
        room_id=to_room_id,
        growth_phase=snapshot.get("growth_phase", "unknown"),
        planted_date=date.fromisoformat(snapshot["planted_date"]) if snapshot.get("planted_date") else date.today(),
        tagged_date=date.fromisoformat(snapshot["tagged_date"]) if snapshot.get("tagged_date") else date.today(),
        mother_plant_id=snapshot.get("mother_plant_id"),
    )
    db.add(plant)
    _record_relay_receipt(db, "plant", plant_id, "moved_in_from_relay", event, room_id=to_room_id)


def _process_harvest_created(db: Session, event: dict) -> None:
    """
    A harvest created on ANY device at a site is synced to every other device too —
    unlike a plant move (which only the destination device absorbs), a harvest is a
    shared, site-wide container that plants growing on *any* device should be able to
    finish into. Without this, harvestPlant() would 404 on every device except the one
    that happened to create the harvest, defeating the point of a multi-device site
    whose growing rooms and post-harvest workflow live on different Pis. See
    docs/architecture.md's audit-relay section.
    """
    harvest_id = event["entity_id"]
    if db.get(Harvest, harvest_id) is not None:
        return  # already synced — redelivery must be a no-op, not a duplicate/conflicting harvest

    snapshot = (event.get("details") or {}).get("harvest_snapshot")
    if not snapshot:
        return  # relayed by an older version without a snapshot — nothing to reconstruct from

    harvest = Harvest(
        id=harvest_id,
        name=snapshot["name"],
        strain=snapshot["strain"],
        source_room_id=snapshot["source_room_id"],
        drying_room_id=snapshot.get("drying_room_id"),
        wet_weight_g=snapshot.get("wet_weight_g", 0.0),
        started_at=datetime.fromisoformat(snapshot["started_at"]) if snapshot.get("started_at") else utcnow(),
    )
    db.add(harvest)
    _record_relay_receipt(db, "harvest", harvest_id, "harvest_synced_from_relay", event, room_id=event.get("room_id"))


def _process_plant_harvested(db: Session, event: dict) -> None:
    """harvest_plant() (POST /plants/{id}/harvest) increments the harvest's
    wet_weight_g and logs a "wet" weigh-in on whichever device the plant lived on —
    that harvest may well have been *created* on a different device (now synced
    there via _process_harvest_created), so every other device needs this same
    weight update applied to its own copy, or their wet_weight_g silently drifts out
    of sync with reality. The plant itself needs no local update here: a plant only
    ever lives on the one device that owns its current room (see _process_plant_moved),
    so this event's origin device is necessarily that plant's real owner already."""
    if _already_relayed(db, event):
        return
    details = event.get("details") or {}
    harvest_id = details.get("harvest_id")
    weight_g = details.get("weight_g")
    if not harvest_id or weight_g is None:
        return
    harvest = db.get(Harvest, harvest_id)
    if harvest is None:
        return  # this harvest hasn't synced here yet — nothing to attach the weight to

    harvest.wet_weight_g += weight_g
    db.add(
        HarvestWeightLog(
            harvest_id=harvest_id, stage="wet", weight_g=weight_g,
            room_id=harvest.source_room_id, actor=event.get("actor", "unknown"),
        )
    )
    _record_relay_receipt(db, "harvest", harvest_id, "harvest_weigh_synced_from_relay", event, room_id=event.get("room_id"))


def _process_harvest_weighed(db: Session, event: dict) -> None:
    """A direct weigh_harvest() checkpoint (wet/dry/cure) — same sync reasoning as
    _process_plant_harvested, for the other endpoint that logs a HarvestWeightLog."""
    if _already_relayed(db, event):
        return
    harvest_id = event["entity_id"]
    harvest = db.get(Harvest, harvest_id)
    if harvest is None:
        return

    details = event.get("details") or {}
    stage, weight_g = details.get("stage"), details.get("weight_g")
    if stage is None or weight_g is None:
        return
    db.add(
        HarvestWeightLog(
            harvest_id=harvest_id, stage=stage, weight_g=weight_g,
            room_id=event.get("room_id") or harvest.source_room_id, actor=event.get("actor", "unknown"),
        )
    )
    _record_relay_receipt(db, "harvest", harvest_id, "harvest_weigh_synced_from_relay", event, room_id=event.get("room_id"))


def _process_harvest_finished(db: Session, event: dict) -> None:
    if _already_relayed(db, event):
        return
    harvest_id = event["entity_id"]
    harvest = db.get(Harvest, harvest_id)
    if harvest is None:
        return

    harvest.status = "finished"
    # The origin device's own record_audit call set finished_at to essentially this
    # same instant — occurred_at on the relayed event itself is that exact timestamp,
    # not something that needs its own snapshot field.
    harvest.finished_at = datetime.fromisoformat(event["occurred_at"])
    _record_relay_receipt(db, "harvest", harvest_id, "harvest_finish_synced_from_relay", event, room_id=event.get("room_id"))


def _process_package_created(db: Session, event: dict) -> None:
    """A package created directly from a harvest is synced everywhere, same
    reasoning as _process_harvest_created — a processed/derivative package (a
    manufacturing-chain step, action "processed" rather than "created") is
    deliberately NOT handled here yet; see this module's process_relay_event
    docstring."""
    if _already_relayed(db, event):
        return
    package_id = event["entity_id"]
    if db.get(Package, package_id) is not None:
        return

    snapshot = (event.get("details") or {}).get("package_snapshot")
    if not snapshot:
        return

    package = Package(
        id=package_id,
        harvest_id=snapshot.get("harvest_id"),
        item_name=snapshot["item_name"],
        weight_g=snapshot["weight_g"],
        room_id=snapshot["room_id"],
        is_production_batch=snapshot.get("is_production_batch", False),
        is_donation=snapshot.get("is_donation", False),
    )
    db.add(package)
    _record_relay_receipt(db, "package", package_id, "package_synced_from_relay", event, room_id=snapshot.get("room_id"))
