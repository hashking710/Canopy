from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from canopy_agent.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Room(Base):
    """
    A monitored area (greenhouse bay, clone room, vault, ... — including the
    top-level "facility" summary card, which is just a room with no live metrics
    of its own). `metric_config` holds the per-metric display config
    (label/unit/decimals) and, for metrics the mock adapter should randomly walk,
    the (min, max, step) range. Metrics marked "derived" are computed by a service
    (e.g. VPD) instead of walked directly.
    """

    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    room_type: Mapped[str] = mapped_column(String, index=True)
    path: Mapped[str] = mapped_column(String)
    subtitle: Mapped[str] = mapped_column(String, default="")
    title: Mapped[str] = mapped_column(String, default="")
    badge: Mapped[str] = mapped_column(String, default="")
    footnote: Mapped[str] = mapped_column(String, default="")
    section: Mapped[str | None] = mapped_column(String, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    tag_count: Mapped[int] = mapped_column(Integer, default=0)
    metric_config: Mapped[dict] = mapped_column(JSON, default=dict)

    # Which SensorAdapter (see adapters/registry.py) polls this room, and any
    # adapter-specific config it needs (e.g. a controller/device id). "mock" needs none.
    adapter_type: Mapped[str] = mapped_column(String, default="mock")
    adapter_config: Mapped[dict] = mapped_column(JSON, default=dict)

    # Set by the poller every cycle (services/poller.py) so a failing adapter is
    # visible in the UI instead of only showing up in backend logs. last_poll_at
    # updates on both success and failure; last_poll_error is cleared on success.
    last_poll_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_poll_error: Mapped[str | None] = mapped_column(String, nullable=True)

    readings: Mapped[list["Reading"]] = relationship(back_populates="room")
    extra_adapters: Mapped[list["RoomAdapter"]] = relationship(back_populates="room", order_by="RoomAdapter.id")


class RoomAdapter(Base):
    """
    An additional sensor adapter polled for a room, beyond its primary
    adapter_type/adapter_config above — e.g. a BLE temp/RH controller plus a
    separate CO2 probe on the same room. The poller (services/poller.py) reads the
    primary adapter first, then each of these in insertion order, merging every
    adapter's returned metrics into one dict for the room — a later adapter's key
    wins on collision (matches the primary-then-extras read order), so config order
    is a meaningful choice, not arbitrary. Kept as its own table rather than turning
    Room.adapter_type/adapter_config into a list, so the overwhelmingly common
    single-adapter case (and every existing room/test/plugin) needs no changes at
    all — this is purely additive.
    """

    __tablename__ = "room_adapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"), index=True)
    adapter_type: Mapped[str] = mapped_column(String)
    adapter_config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    room: Mapped["Room"] = relationship(back_populates="extra_adapters")


class Reading(Base):
    """One polled or derived value for one metric on one room, at one point in time."""

    __tablename__ = "readings"
    __table_args__ = (
        # Every read of this table (the readings endpoint behind RoomDetail's
        # sparkline/history list, and retention.py's rollup scan) filters by
        # room_id + metric together, then orders by ts — the separate single-column
        # indexes below can each narrow the search but can't satisfy the combined
        # filter + order + limit in one pass. On a Pi logging every ~5s across
        # several rooms/metrics, this table is the single hottest one in the
        # database, so this is the index that actually matters most here.
        Index("ix_readings_room_metric_ts", "room_id", "metric", "ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"), index=True)
    metric: Mapped[str] = mapped_column(String, index=True)
    value: Mapped[float] = mapped_column(Float)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    room: Mapped["Room"] = relationship(back_populates="readings")


class ReadingRollup(Base):
    """
    Hourly aggregate of Reading rows, computed by services/retention.py so raw
    per-poll readings (one every ~5s, forever) don't grow unbounded on a Pi's SD card.
    A raw reading is only pruned once its hour's rollup exists here — retention is
    additive-then-prune, never lossy for data it hasn't safely aggregated yet.
    """

    __tablename__ = "reading_rollups"
    __table_args__ = (UniqueConstraint("room_id", "metric", "bucket_start", name="uq_reading_rollup_bucket"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"), index=True)
    metric: Mapped[str] = mapped_column(String, index=True)
    bucket_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    avg_value: Mapped[float] = mapped_column(Float)
    min_value: Mapped[float] = mapped_column(Float)
    max_value: Mapped[float] = mapped_column(Float)
    sample_count: Mapped[int] = mapped_column(Integer)


class AlertRule(Base):
    """A threshold to watch on one room's metric — evaluated every poll cycle by
    services/alerts.py. The whole point of monitoring software is catching a problem
    while nobody's looking at the dashboard; this is what makes that possible."""

    __tablename__ = "alert_rules"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"), index=True)
    metric: Mapped[str] = mapped_column(String)
    condition: Mapped[str] = mapped_column(String)  # "gt" | "lt"
    threshold: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String, default="warning")  # "warning" | "critical"
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AlertEvent(Base):
    """
    One breach of an AlertRule. Opened when a reading first crosses the threshold,
    closed (resolved_at set) once a later reading is back in range — so this table's
    open rows (resolved_at IS NULL) are always "what's actively wrong right now",
    not a running log every poll cycle re-adds to.
    """

    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(ForeignKey("alert_rules.id"), index=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"), index=True)
    metric: Mapped[str] = mapped_column(String)
    value: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float] = mapped_column(Float)
    condition: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)

    triggered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String, nullable=True)
