import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from canopy_agent.adapters.registry import available_adapter_types
from canopy_agent.deps import get_db
from canopy_agent.models import AlertEvent, AlertRule, Reading, ReadingRollup, Room, RoomAdapter
from canopy_agent.schemas import ReadingPoint, RoomAdapterOut, RoomConfigOut, RoomOut
from canopy_agent.stats import get_latest_values, room_payload

router = APIRouter(prefix="/api/rooms", tags=["rooms"])

_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class CreateRoomRequest(BaseModel):
    id: str
    room_type: str
    title: str = ""
    subtitle: str = ""
    badge: str = ""
    footnote: str = ""
    section: str | None = None
    sort_order: int = 0
    metric_config: dict = {}
    adapter_type: str = "mock"
    adapter_config: dict = {}


class UpdateRoomRequest(BaseModel):
    title: str | None = None
    subtitle: str | None = None
    badge: str | None = None
    footnote: str | None = None
    section: str | None = None
    sort_order: int | None = None
    metric_config: dict | None = None
    adapter_type: str | None = None
    adapter_config: dict | None = None


def _validate_id(room_id: str) -> None:
    if not _ID_PATTERN.match(room_id):
        raise HTTPException(
            status_code=400,
            detail="room id must be lowercase letters, numbers, hyphens, or underscores, starting with a letter or number (max 64 chars)",
        )


def _validate_metric_config(metric_config: dict, adapter_type: str) -> None:
    for key, cfg in metric_config.items():
        if not isinstance(cfg, dict) or not cfg.get("label"):
            raise HTTPException(
                status_code=400, detail=f"metric_config['{key}'] must be an object with at least a non-empty 'label'"
            )
        # Caught here, not just left to surface later as a cryptic poll failure — the
        # mock adapter (adapters/mock.py) needs a range to walk within for every
        # non-derived metric; a real adapter reads the value from hardware instead and
        # doesn't need this.
        if adapter_type == "mock" and not cfg.get("derived") and ("min" not in cfg or "max" not in cfg):
            raise HTTPException(
                status_code=400,
                detail=f"metric_config['{key}'] uses the mock adapter but is missing 'min'/'max' (or mark it \"derived\")",
            )


def _validate_adapter_type(adapter_type: str) -> None:
    installed = available_adapter_types()
    if adapter_type not in installed:
        raise HTTPException(
            status_code=400,
            detail=f"unknown adapter_type '{adapter_type}' — installed: {sorted(installed)}. Is the plugin package installed?",
        )


def _to_room_out(room: Room, db: Session) -> RoomOut:
    values = get_latest_values(db, room.id)
    return RoomOut(**room_payload(room, values))


@router.get("/adapters/available")
def list_available_adapters() -> list[dict]:
    """What a room's adapter_type can actually be set to on this device — installed
    plugins only, so the room-creation UI shows real options instead of guessing at
    what's available (see plugins/ and docs/plugin-development.md)."""
    return [
        {
            "adapter_type": adapter_type,
            "plugin_name": adapter_cls.plugin_name,
            "plugin_description": adapter_cls.plugin_description,
            "config_schema": adapter_cls.config_schema,
            "required_env_vars": adapter_cls.required_env_vars,
        }
        for adapter_type, adapter_cls in sorted(available_adapter_types().items())
    ]


@router.get("", response_model=list[RoomOut])
def list_rooms(db: Session = Depends(get_db)) -> list[RoomOut]:
    rooms = (
        db.execute(select(Room).where(Room.room_type != "facility").order_by(Room.sort_order))
        .scalars()
        .all()
    )
    return [_to_room_out(room, db) for room in rooms]


@router.get("/{room_id}", response_model=RoomOut)
def get_room(room_id: str, db: Session = Depends(get_db)) -> RoomOut:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="room not found")
    return _to_room_out(room, db)


@router.get("/{room_id}/config", response_model=RoomConfigOut)
def get_room_config(room_id: str, db: Session = Depends(get_db)) -> RoomConfigOut:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="room not found")
    return RoomConfigOut(
        adapter_type=room.adapter_type, metric_config=room.metric_config, adapter_config=room.adapter_config,
        extra_adapters=[
            RoomAdapterOut(id=a.id, adapter_type=a.adapter_type, adapter_config=a.adapter_config)
            for a in room.extra_adapters
        ],
    )


@router.post("", response_model=RoomOut)
def create_room(body: CreateRoomRequest, db: Session = Depends(get_db)) -> RoomOut:
    if body.room_type == "facility":
        raise HTTPException(status_code=400, detail="use POST /api/facility to set up the facility, not this endpoint")
    _validate_id(body.id)
    _validate_metric_config(body.metric_config, body.adapter_type)
    _validate_adapter_type(body.adapter_type)

    if db.get(Room, body.id) is not None:
        raise HTTPException(status_code=400, detail=f"a room with id '{body.id}' already exists")

    room = Room(
        id=body.id, room_type=body.room_type, path=body.id,
        title=body.title, subtitle=body.subtitle, badge=body.badge, footnote=body.footnote,
        section=body.section, sort_order=body.sort_order, metric_config=body.metric_config,
        adapter_type=body.adapter_type, adapter_config=body.adapter_config,
    )
    db.add(room)
    db.commit()
    return _to_room_out(room, db)


@router.put("/{room_id}", response_model=RoomOut)
def update_room(room_id: str, body: UpdateRoomRequest, db: Session = Depends(get_db)) -> RoomOut:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="room not found")

    updates = body.model_dump(exclude_unset=True)
    if "metric_config" in updates:
        # Validated against whichever adapter_type will actually be in effect after
        # this update — the new one if it's changing, otherwise the room's existing one.
        _validate_metric_config(updates["metric_config"], updates.get("adapter_type", room.adapter_type))
    if "adapter_type" in updates:
        _validate_adapter_type(updates["adapter_type"])
    for key, value in updates.items():
        setattr(room, key, value)

    db.commit()
    return _to_room_out(room, db)


@router.delete("/{room_id}")
def delete_room(room_id: str, db: Session = Depends(get_db)) -> dict:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="room not found")
    if room.room_type == "facility":
        raise HTTPException(status_code=400, detail="the facility row can't be deleted from here")

    # SQLite doesn't enforce foreign keys in this project (see db.py), so related rows
    # need explicit cleanup here or they'd linger as orphans referencing a room that no
    # longer exists — cheap correctness now, not a "nice to have."
    for rule_id in db.execute(select(AlertRule.id).where(AlertRule.room_id == room_id)).scalars().all():
        db.execute(delete(AlertEvent).where(AlertEvent.rule_id == rule_id))
    db.execute(delete(AlertRule).where(AlertRule.room_id == room_id))
    db.execute(delete(ReadingRollup).where(ReadingRollup.room_id == room_id))
    db.execute(delete(Reading).where(Reading.room_id == room_id))
    db.execute(delete(RoomAdapter).where(RoomAdapter.room_id == room_id))
    db.delete(room)
    db.commit()
    return {"id": room_id, "deleted": True}


class AddRoomAdapterRequest(BaseModel):
    adapter_type: str
    adapter_config: dict = {}


@router.post("/{room_id}/adapters", response_model=RoomAdapterOut)
def add_room_adapter(room_id: str, body: AddRoomAdapterRequest, db: Session = Depends(get_db)) -> RoomAdapterOut:
    """Adds an *additional* adapter for this room, polled alongside its primary
    adapter_type/adapter_config every cycle and merged into one reading (see
    services/poller.py) — e.g. a BLE temp/RH controller plus a separate CO2 probe on
    the same room. The room's primary adapter is unaffected; use PUT /{room_id} to
    change that one."""
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="room not found")
    _validate_adapter_type(body.adapter_type)

    extra = RoomAdapter(room_id=room_id, adapter_type=body.adapter_type, adapter_config=body.adapter_config)
    db.add(extra)
    db.commit()
    return RoomAdapterOut(id=extra.id, adapter_type=extra.adapter_type, adapter_config=extra.adapter_config)


@router.delete("/{room_id}/adapters/{adapter_id}")
def remove_room_adapter(room_id: str, adapter_id: int, db: Session = Depends(get_db)) -> dict:
    extra = db.get(RoomAdapter, adapter_id)
    if extra is None or extra.room_id != room_id:
        raise HTTPException(status_code=404, detail="extra adapter not found on this room")
    db.delete(extra)
    db.commit()
    return {"id": adapter_id, "deleted": True}


@router.get("/{room_id}/readings", response_model=list[ReadingPoint])
def get_room_readings(
    room_id: str,
    metric: str | None = None,
    limit: int = Query(default=100, le=1000),
    db: Session = Depends(get_db),
) -> list[ReadingPoint]:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="room not found")

    metric = metric or next(iter(room.metric_config), None)
    if metric is None:
        return []

    rows = (
        db.execute(
            select(Reading)
            .where(Reading.room_id == room_id, Reading.metric == metric)
            .order_by(Reading.ts.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [ReadingPoint(ts=r.ts.isoformat(), value=r.value) for r in reversed(rows)]
