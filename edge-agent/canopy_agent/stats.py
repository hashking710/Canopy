from sqlalchemy import func, select
from sqlalchemy.orm import Session

from canopy_agent.models import Reading, Room
from canopy_agent.schemas import MetricOut


def get_latest_values(db: Session, room_id: str) -> dict[str, float]:
    """Most recent value per metric for a room, via one row-per-metric latest-timestamp query."""
    latest_ts = (
        select(Reading.metric, func.max(Reading.ts).label("ts"))
        .where(Reading.room_id == room_id)
        .group_by(Reading.metric)
        .subquery()
    )
    rows = db.execute(
        select(Reading.metric, Reading.value)
        .join(
            latest_ts,
            (Reading.metric == latest_ts.c.metric) & (Reading.ts == latest_ts.c.ts),
        )
        .where(Reading.room_id == room_id)
    ).all()
    return {metric: value for metric, value in rows}


def get_latest_values_for_rooms(db: Session, room_ids: list[str]) -> dict[str, dict[str, float]]:
    """Same as get_latest_values, but for every room in one query instead of one query
    per room — used by the MQTT publish path (poller.py's _publish_all_room_states),
    which needs this for every room, every poll cycle, not just one room per request
    like the REST endpoint that get_latest_values itself serves."""
    if not room_ids:
        return {}

    latest_ts = (
        select(Reading.room_id, Reading.metric, func.max(Reading.ts).label("ts"))
        .where(Reading.room_id.in_(room_ids))
        .group_by(Reading.room_id, Reading.metric)
        .subquery()
    )
    rows = db.execute(
        select(Reading.room_id, Reading.metric, Reading.value).join(
            latest_ts,
            (Reading.room_id == latest_ts.c.room_id)
            & (Reading.metric == latest_ts.c.metric)
            & (Reading.ts == latest_ts.c.ts),
        )
    ).all()

    result: dict[str, dict[str, float]] = {room_id: {} for room_id in room_ids}
    for room_id, metric, value in rows:
        result[room_id][metric] = value
    return result


def format_stats(room: Room, values: dict[str, float]) -> list[MetricOut]:
    stats: list[MetricOut] = []
    for key, cfg in room.metric_config.items():
        if key not in values:
            continue
        stats.append(
            MetricOut(
                key=key,
                label=cfg["label"],
                unit=cfg.get("unit", ""),
                value=round(values[key], cfg.get("decimals", 1)),
                decimals=cfg.get("decimals", 1),
            )
        )
    return stats


def room_payload(room: Room, values: dict[str, float]) -> dict:
    """
    The full JSON-able shape of a room, shared by the REST routers and the MQTT
    publisher so "what a room looks like on the wire" is defined in exactly one place.
    """
    return {
        "id": room.id,
        "room_type": room.room_type,
        "path": room.path,
        "subtitle": room.subtitle,
        "title": room.title,
        "badge": room.badge,
        "footnote": room.footnote,
        "section": room.section,
        "tag_count": room.tag_count,
        "stats": [stat.model_dump() for stat in format_stats(room, values)],
        "last_poll_at": room.last_poll_at.isoformat() if room.last_poll_at else None,
        "last_poll_error": room.last_poll_error,
    }


# room_types that count toward the facility's "plants on site" tallies, in display order
FACILITY_TALLY_ROOM_TYPES = [
    ("greenhouse", "greenhouse"),
    ("mother_room", "mother room"),
    ("clone_room", "clone room"),
]


def facility_payload(db: Session, facility: Room) -> dict:
    tallies: dict[str, int] = {}
    for room_type, _label in FACILITY_TALLY_ROOM_TYPES:
        rooms = db.execute(select(Room).where(Room.room_type == room_type)).scalars().all()
        tallies[room_type] = sum(r.tag_count for r in rooms)
    total_tagged = sum(tallies.values())

    stats = [MetricOut(key="total_tagged", label="total tagged", unit="", value=total_tagged, decimals=0)]
    stats += [
        MetricOut(key=room_type, label=label, unit="", value=tallies[room_type], decimals=0)
        for room_type, label in FACILITY_TALLY_ROOM_TYPES
    ]

    return {
        "id": facility.id,
        "room_type": facility.room_type,
        "path": facility.path,
        "subtitle": facility.subtitle,
        "title": facility.title,
        "badge": facility.badge,
        "footnote": facility.footnote,
        "section": facility.section,
        "tag_count": total_tagged,
        "stats": [stat.model_dump() for stat in stats],
    }
