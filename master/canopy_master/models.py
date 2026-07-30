from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from canopy_master.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RelayedAuditEntry(Base):
    """
    A durable, append-only mirror of every audit-relay event this master has ever
    seen, across every device at every site — closing a gap this project's own
    architecture doc calls out directly: "the master/site-server gaining real
    persistence for cross-device reconciliation and consolidated reporting... a
    durable site-level record of every device's history is still a real gap" (see
    docs/architecture.md, audit-relay section). Each edge-agent's own SQLite DB
    remains the real system of record for its own hash-chained history — this table
    is a read-side AGGREGATE for "show me everything that happened, across every
    device, in one place," not a replacement for any device's local chain, and not
    itself hash-chained (that guarantee still lives on the originating device; this
    just keeps a durable copy of what it published).

    Deduplicated on (site_id, origin_device_id, origin_entry_id) — the same triple
    that already uniquely identifies one real audit entry system-wide — since MQTT
    QoS 1 is at-least-once delivery and this table may see the same message more than
    once across reconnects.
    """

    __tablename__ = "relayed_audit_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[str] = mapped_column(String, index=True)
    origin_device_id: Mapped[str] = mapped_column(String)
    origin_entry_id: Mapped[int] = mapped_column(Integer)  # AuditLogEntry.id on the device that created it
    entity_type: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String)
    room_id: Mapped[str | None] = mapped_column(String, nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    entry_hash: Mapped[str] = mapped_column(String)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint("site_id", "origin_device_id", "origin_entry_id", name="uq_relayed_audit_origin"),
    )
