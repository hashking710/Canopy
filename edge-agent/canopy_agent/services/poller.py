import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from canopy_agent.adapters.registry import get_adapter
from canopy_agent.db import SessionLocal
from canopy_agent.models import Reading, Room
from canopy_agent.services.alerts import dispatch_alert_notifications, evaluate_alerts_for_room
from canopy_agent.services.audit_relay import publish_pending_audit_events
from canopy_agent.services.mqtt_publisher import mqtt_enabled, publish_states
from canopy_agent.services.vpd import vpd_kpa
from canopy_agent.stats import facility_payload, format_stats, get_latest_values_for_rooms, room_payload
from canopy_agent.ws_manager import ws_manager

logger = logging.getLogger("canopy_agent.poller")

POLL_INTERVAL_SECONDS = 5
# Third-party adapter plugins can do arbitrary I/O in read(); a hung one (bad network
# call, deadlocked driver) must not stall every other room's poll indefinitely — this
# bounds how long any single adapter gets before we give up on it for the cycle.
ADAPTER_READ_TIMEOUT_SECONDS = 10


async def poll_forever() -> None:
    while True:
        try:
            await poll_once()
        except Exception:
            logger.exception("poll cycle failed")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def poll_once() -> None:
    db = SessionLocal()
    try:
        rooms = db.execute(select(Room)).scalars().all()

        # Adapter I/O (network calls to a cloud API, serial/hardware reads) runs
        # concurrently across every room — with real adapters (not the near-instant
        # mock), sequential polling would make total cycle time scale linearly with
        # room count, degrading live-update latency as a facility grows. Each read is
        # already bounded by its own timeout, so gather can't hang on one bad adapter.
        # DB writes stay strictly sequential afterward, in this coroutine: a single
        # SQLAlchemy Session isn't safe to share across concurrently-interleaved
        # add/commit calls, so results are collected first and only written once
        # every read has settled — isolated per room either way, same as before.
        results = await asyncio.gather(*(_read_room(room) for room in rooms), return_exceptions=True)

        for room, result in zip(rooms, results):
            if isinstance(result, BaseException):
                logger.exception(
                    "failed to poll room '%s' (adapter_type=%s)", room.id, room.adapter_type, exc_info=result
                )
                _record_poll_health(db, room, error=str(result) or result.__class__.__name__)
                continue
            try:
                await _write_room_reading(db, room, result)
                _record_poll_health(db, room, error=None)
            except Exception as exc:
                logger.exception("failed to record reading for room '%s' (adapter_type=%s)", room.id, room.adapter_type)
                _record_poll_health(db, room, error=str(exc) or exc.__class__.__name__)
        db.commit()

        if mqtt_enabled():
            await _publish_all_room_states(db, rooms)
            await publish_pending_audit_events(db)
    finally:
        db.close()


def _record_poll_health(db: Session, room: Room, error: str | None) -> None:
    """Surfaces adapter failures in the UI (see Room.last_poll_error) instead of only
    in backend logs — a failing sensor should be obvious from the dashboard, not
    something you discover by tailing a log file days later."""
    room.last_poll_at = datetime.now(timezone.utc)
    room.last_poll_error = error


async def _read_room(room: Room) -> dict[str, float]:
    """Adapter I/O only — no DB access — so this is safe to run concurrently across
    rooms via asyncio.gather (see poll_once)."""
    adapter = get_adapter(room)
    try:
        values = await asyncio.wait_for(adapter.read(room), timeout=ADAPTER_READ_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        raise RuntimeError(
            f"adapter_type '{room.adapter_type}' didn't respond within {ADAPTER_READ_TIMEOUT_SECONDS}s"
        ) from None

    for key, cfg in room.metric_config.items():
        # Only fill in the derived value if the adapter didn't already report one
        # itself (e.g. a real sensor or the AC Infinity API reporting its own VPD).
        if cfg.get("derived") == "vpd" and key not in values and "temp_f" in values and "rh_pct" in values:
            values[key] = vpd_kpa(values["temp_f"], values["rh_pct"])

    return values


async def _write_room_reading(db: Session, room: Room, values: dict[str, float]) -> None:
    if not values:
        return

    db.add_all(Reading(room_id=room.id, metric=metric, value=value) for metric, value in values.items())
    newly_opened_alerts = evaluate_alerts_for_room(db, room.id, values)
    db.commit()

    await ws_manager.broadcast(
        {
            "type": "reading_update",
            "room_id": room.id,
            "stats": [stat.model_dump() for stat in format_stats(room, values)],
        }
    )
    await dispatch_alert_notifications(newly_opened_alerts, room.id)


async def _publish_all_room_states(db: Session, rooms: list[Room]) -> None:
    """Every room's current state, republished each cycle regardless of whether it
    changed this cycle — a master aggregator that (re)connects mid-cycle still needs
    the full picture, not just what happened to update since it last looked."""
    non_facility_ids = [room.id for room in rooms if room.room_type != "facility"]
    latest_values = get_latest_values_for_rooms(db, non_facility_ids)

    payloads = []
    for room in rooms:
        if room.room_type == "facility":
            payloads.append(facility_payload(db, room))
        else:
            payloads.append(room_payload(room, latest_values.get(room.id, {})))
    await publish_states(payloads)
