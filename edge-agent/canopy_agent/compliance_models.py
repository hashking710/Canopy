"""
Compliance/track-and-trace domain model.

Field and lifecycle choices here are grounded in METRC's real object model (the
track-and-trace system used by most legal US cannabis states) — not because we sync to
METRC yet (we don't have credentials to verify against), but so that a future
`MetrcComplianceSync` implementation is a mapping exercise, not a redesign. In
particular:

- Plants are tracked as an untagged, count-based `PlantBatch` (an "immature lot") until
  moved to a tracked location or flowering, at which point each one becomes an
  individually tagged `Plant`. This mirrors METRC's actual two-tier model, not a
  simplification of it — see PlantBatch's UntrackedCount/TrackedCount/PackagedCount/
  HarvestedCount/DestroyedCount, which is METRC's own real field set for exactly this
  reason: the sum of those must always reconcile to the batch's original count.
- Waste destruction records a method/material/reason (e.g. "Grinder"/"Soil"/
  "Contamination"), matching METRC's `destroyplants` action fields, and must be
  reportable within 3 business days of the actual destruction — a real METRC rule, see
  `services/compliance_deadlines.py`.
"""

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from canopy_agent.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Operator(Base):
    """
    A named identity for attributing compliance actions. Deliberately not a login
    account — API access stays the shared-secret token from docs/architecture.md's
    auth section, chosen over full user accounts for a single-operator LAN appliance.
    This solves a different, narrower problem: before this existed, "actor" on every
    compliance action was a free-text field anyone could type any name into, which
    undermines an audit trail's whole point. Selecting from a constrained list of
    registered operators — optionally PIN-confirmed for high-stakes actions like plant
    destruction — is real attribution without the cost of building full auth.

    `role` (added later, migration 8f1c4a2b9e3d) is a second, narrower thing than
    that same auth question: given everyone already shares the one API token, a role
    isn't about keeping an untrusted party out — it's about a legitimate dashboard
    user picking "who I am" and the API then refusing to let a viewer-role pick
    destroy plants or change facility credentials, same spirit as the PIN
    confirmation already required for destruction. See services/operators.py's
    ROLE_RANK for the hierarchy and require_role() for the enforcement helper.
    """

    __tablename__ = "operators"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    pin_hash: Mapped[str | None] = mapped_column(String, nullable=True)  # PBKDF2, see services/operators.py
    pin_salt: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, default="operator")  # "viewer" | "operator" | "admin"
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Personal notification preferences (migration pending, added alongside menu sync).
    # Self-service, not role-derived: the backend just stores whatever's submitted —
    # any role-based "sensible default" is a frontend suggestion only (see
    # OperatorPicker.tsx), never enforced server-side. Off by default for every
    # existing operator (a new opt-in capability, not a new restriction — no deadlock
    # concern like `role`'s own migration had to work around).
    notify_email: Mapped[str | None] = mapped_column(String, nullable=True)
    notify_on_alerts: Mapped[bool] = mapped_column(default=False)
    notify_on_system_errors: Mapped[bool] = mapped_column(default=False)
    notify_min_severity: Mapped[str] = mapped_column(String, default="critical")  # "warning" | "critical"


class Strain(Base):
    """
    A genetics registry entry — optional structured metadata a `PlantBatch`/`Plant`/
    `Harvest` can link to via `strain_id`, layered on top of (not replacing) their own
    free-text `strain` field. Exists for two things the free-text field can't carry:
    lineage/type for display, and a "typical" potency to fall back on for menu sync
    (see services/menu_data.py) when a specific package has no lab test of its own yet.

    Deliberately optional/additive rather than a migration of existing `strain` columns
    to a hard foreign key — that would mean either a risky backfill (matching free text
    to registry entries is lossy/ambiguous) or breaking every existing compliance record
    that doesn't cleanly match a registry entry. A facility that doesn't care about the
    registry can keep typing strain names exactly as before.
    """

    __tablename__ = "strains"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    lineage: Mapped[str] = mapped_column(String, default="")  # e.g. "OG Kush x Sour Diesel"
    strain_type: Mapped[str] = mapped_column(String, default="unknown")  # indica | sativa | hybrid | unknown
    description: Mapped[str] = mapped_column(String, default="")
    thc_pct_typical: Mapped[float | None] = mapped_column(Float, nullable=True)
    cbd_pct_typical: Mapped[float | None] = mapped_column(Float, nullable=True)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PlantBatch(Base):
    """An immature, count-based plant lot — METRC's PlantBatch. Individual plants are
    split off into `Plant` rows (tagged) as they're moved to flowering/canopy."""

    __tablename__ = "plant_batches"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    batch_type: Mapped[str] = mapped_column(String)  # "Seed" | "Clone"
    strain: Mapped[str] = mapped_column(String)
    strain_id: Mapped[str | None] = mapped_column(ForeignKey("strains.id"), nullable=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"), index=True)
    planted_date: Mapped[date] = mapped_column(Date)
    source_batch_id: Mapped[str | None] = mapped_column(ForeignKey("plant_batches.id"), nullable=True)

    untracked_count: Mapped[int] = mapped_column(Integer, default=0)
    tracked_count: Mapped[int] = mapped_column(Integer, default=0)
    packaged_count: Mapped[int] = mapped_column(Integer, default=0)
    harvested_count: Mapped[int] = mapped_column(Integer, default=0)
    destroyed_count: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[str] = mapped_column(String, default="active")  # active | inactive

    plants: Mapped[list["Plant"]] = relationship(back_populates="batch")


class Plant(Base):
    """An individually tagged plant (post-immature-lot). METRC assigns a plant tag
    when a plant is moved to a designated canopy area or begins flowering."""

    __tablename__ = "plants"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # the plant tag/label
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("plant_batches.id"), nullable=True)
    strain: Mapped[str] = mapped_column(String)
    strain_id: Mapped[str | None] = mapped_column(ForeignKey("strains.id"), nullable=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"), index=True)
    growth_phase: Mapped[str] = mapped_column(String)  # "Vegetative" | "Flowering"
    planted_date: Mapped[date] = mapped_column(Date)
    tagged_date: Mapped[date] = mapped_column(Date)
    mother_plant_id: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(String, default="active")  # active | harvested | destroyed

    batch: Mapped["PlantBatch | None"] = relationship(back_populates="plants")


class Harvest(Base):
    """A harvest batch — METRC requires harvest names be unique and strain-specific."""

    __tablename__ = "harvests"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    strain: Mapped[str] = mapped_column(String)
    strain_id: Mapped[str | None] = mapped_column(ForeignKey("strains.id"), nullable=True)
    source_room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"))
    drying_room_id: Mapped[str | None] = mapped_column(ForeignKey("rooms.id"), nullable=True)
    wet_weight_g: Mapped[float] = mapped_column(Float)

    status: Mapped[str] = mapped_column(String, default="active")  # active | finished
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    weight_logs: Mapped[list["HarvestWeightLog"]] = relationship(back_populates="harvest")
    packages: Mapped[list["Package"]] = relationship(back_populates="harvest")


class HarvestWeightLog(Base):
    """A weight checkpoint along a harvest's wet -> dry -> cure lineage."""

    __tablename__ = "harvest_weight_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    harvest_id: Mapped[str] = mapped_column(ForeignKey("harvests.id"), index=True)
    stage: Mapped[str] = mapped_column(String)  # "wet" | "dry" | "cure"
    weight_g: Mapped[float] = mapped_column(Float)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    actor: Mapped[str] = mapped_column(String, default="unknown")

    harvest: Mapped["Harvest"] = relationship(back_populates="weight_logs")


class Package(Base):
    """
    A tagged, trackable package — METRC's unit of transfer/sale. Created either
    directly from a harvest (flower/trim going straight to packaging) or, via
    `source_package_id`, from another package — the latter is how a manufacturing/
    extraction chain is represented: source material -> BHO/CO2/ethanol extraction ->
    crude oil (a package) -> winterization -> distillation -> distillate (another
    package), each step its own row with its own weight and a `process_method`,
    walkable back to the origin harvest via repeated `source_package_id` lookups.
    Deliberately single-source per package (not multi-input blending) — matches how
    the rest of this compliance model stays close to METRC's own real object shapes
    without taking on a bigger modeling problem (blending multiple source lots) this
    project doesn't need yet.
    """

    __tablename__ = "packages"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # the package tag/label
    harvest_id: Mapped[str | None] = mapped_column(ForeignKey("harvests.id"), nullable=True)
    source_package_id: Mapped[str | None] = mapped_column(ForeignKey("packages.id"), nullable=True)
    process_method: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g. "BHO Extraction", "Winterization", "Short-Path Distillation" — only set when source_package_id is
    process_yield_pct: Mapped[float | None] = mapped_column(Float, nullable=True)  # this package's weight_g / source package's weight_g * 100
    item_name: Mapped[str] = mapped_column(String)
    weight_g: Mapped[float] = mapped_column(Float)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"), index=True)
    # What this package is listed for sale at, for menu sync (services/menu_data.py) to
    # push out — optional, and deliberately not a real pricing/tiers system. Canopy
    # doesn't own pricing; the POS/dispensary does. This is just "what to list it at"
    # for a facility that wants Canopy to supply one at all.
    list_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_production_batch: Mapped[bool] = mapped_column(default=False)
    is_donation: Mapped[bool] = mapped_column(default=False)

    status: Mapped[str] = mapped_column(String, default="active")  # active | sold | destroyed | transferred | processed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    harvest: Mapped["Harvest | None"] = relationship(back_populates="packages")
    source_package: Mapped["Package | None"] = relationship(remote_side=[id])


class LabTest(Base):
    """
    A lab result recorded against a package — required by most states before a
    solvent-extracted concentrate (BHO/CO2/ethanol) can be sold/transferred, and
    common for potency/contaminant screening more broadly. See
    compliance_rules/base.py's `testing_required_for_solvent_extracts` for which
    states' regulations this project has actually verified require it. Not a METRC
    API integration (no state lab-results feed exists to pull from here) — this is
    Canopy's own record of a result a lab reported back, same as everything else in
    this module.
    """

    __tablename__ = "lab_tests"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    package_id: Mapped[str] = mapped_column(ForeignKey("packages.id"), index=True)
    lab_name: Mapped[str] = mapped_column(String)
    test_type: Mapped[str] = mapped_column(String)  # "residual_solvents" | "potency" | "microbial" | "pesticides" | "heavy_metals" | "other"
    result: Mapped[str] = mapped_column(String)  # "pass" | "fail" | "pending"
    thc_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    cbd_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(String, default="")
    tested_at: Mapped[date] = mapped_column(Date)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    recorded_by: Mapped[str] = mapped_column(String, default="unknown")
    # The original COA (Certificate of Analysis) document the lab sent back, kept on
    # file for inspections — attached as-is, never parsed. coa_filename is what the
    # uploader named it (shown in the UI); coa_stored_path is where it actually lives
    # on disk (services/coa_storage.py), a generated name so nothing in the upload
    # path (including the original filename) is trusted as a filesystem path.
    coa_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    coa_stored_path: Mapped[str | None] = mapped_column(String, nullable=True)


class WasteEvent(Base):
    """
    Plant, batch, harvest, or package waste. The deadline to report this to the state
    depends on which state's rules apply (CANOPY_COMPLIANCE_STATE) — it is NOT a fixed
    METRC-wide number; see compliance_rules/ for per-state figures and sourcing, and
    services/compliance_deadlines.py for how the deadline is computed.
    """

    __tablename__ = "waste_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String)  # plant | plant_batch | harvest | package
    source_id: Mapped[str] = mapped_column(String)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"), index=True)

    waste_type: Mapped[str] = mapped_column(String)  # e.g. "Plant Material", "Fibrous", "Root Ball"
    method: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g. "Grinder", "Compost"
    material: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g. "Soil"
    reason: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g. "Contamination", "Male Plants"
    weight_g: Mapped[float] = mapped_column(Float)
    note: Mapped[str] = mapped_column(String, default="")

    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)  # when destruction happened
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)  # when logged in Canopy
    reported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # when actually filed w/ the state
    actor: Mapped[str] = mapped_column(String, default="unknown")
    witnessed_by: Mapped[str | None] = mapped_column(String, nullable=True)  # a second operator's name, optional


class AuditLogEntry(Base):
    """
    Generic chain-of-custody trail: who did what, to what, when. Every compliance-
    mutating action in the compliance router writes one of these via services/audit.py,
    which also hash-chains every entry to the one before it (prev_hash/entry_hash) —
    a normal database row can be edited in place with no trace, which defeats the
    point of an audit trail for something an inspector might rely on. Editing a
    historical entry breaks the chain from that point forward, and
    services/audit.py's verify_audit_chain() detects exactly that.

    origin_device_id/origin_entry_hash exist for cross-device continuity: when a plant
    moves from a room on one device to a room on another (see services/audit_relay.py),
    the receiving device's "moved in" entry sets these to point back at the sending
    device's own "moved out" entry. This does NOT create one global hash chain across
    devices — each device's chain stays independently verifiable via its own
    prev_hash/entry_hash — it's an explicit cross-reference a verifier can follow to
    stitch two devices' chains together at the handoff point, not a distributed
    consensus mechanism. Null for the overwhelming majority of entries, which never
    cross a device boundary at all.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String, index=True)  # plant | plant_batch | harvest | package | room
    entity_id: Mapped[str] = mapped_column(String, index=True)
    action: Mapped[str] = mapped_column(String)  # created | moved | phase_changed | harvested | destroyed | ...
    actor: Mapped[str] = mapped_column(String, default="unknown")
    room_id: Mapped[str | None] = mapped_column(ForeignKey("rooms.id"), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    prev_hash: Mapped[str] = mapped_column(String)
    entry_hash: Mapped[str] = mapped_column(String, index=True)

    origin_device_id: Mapped[str | None] = mapped_column(String, nullable=True)
    origin_entry_hash: Mapped[str | None] = mapped_column(String, nullable=True)


class RelayCursor(Base):
    """
    Tracks how far this device has gotten through the cross-device relay, in each
    direction, so a restart doesn't have to choose between re-sending everything or
    risking a gap. Always exactly one row per `name`. Duplicate redelivery is expected
    and must stay safe on the receiving side (see services/audit_relay.py) — this is an
    optimization to avoid *unnecessary* redelivery, not a guarantee against it, since
    the underlying transport (MQTT at-least-once, or an HTTP poll that could be
    interrupted after processing but before advancing the cursor) can't provide
    exactly-once delivery.
    """

    __tablename__ = "relay_cursors"

    name: Mapped[str] = mapped_column(String, primary_key=True)  # "publish" | "inbox"
    position: Mapped[int] = mapped_column(Integer, default=0)


class PhysicalCount(Base):
    """A manual plant recount for a room, reconciled against the system's live count
    at that moment — most jurisdictions require periodic physical counts matching the
    tracking system, and a mismatch here is exactly what an inspection would flag."""

    __tablename__ = "physical_counts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"), index=True)
    counted_value: Mapped[int] = mapped_column(Integer)
    system_value_at_time: Mapped[int] = mapped_column(Integer)
    counted_by: Mapped[str] = mapped_column(String, default="unknown")
    counted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    note: Mapped[str] = mapped_column(String, default="")

    @property
    def discrepancy(self) -> int:
        return self.counted_value - self.system_value_at_time


class FacilityComplianceState(Base):
    """
    Which state's compliance ruleset (compliance_rules/) this facility actually
    operates under — a fact about the facility's real legal jurisdiction, not a
    display preference. Deliberately NOT the same kind of thing as a frontend
    Settings-page/localStorage toggle (timezone, temp unit): every operator viewing
    this dashboard must see the same jurisdiction, and changing it is significant
    enough to require an attributed, audit-logged action (see services/facility_state.py
    and the audit_log entity_type "facility"), same bar as any other compliance-mutating
    endpoint in this router.

    Always exactly one row, id=FACILITY_STATE_ROW_ID (same "always exactly one row"
    pattern as RelayCursor). No row at all means "never explicitly set" — falls back to
    CANOPY_COMPLIANCE_STATE / the registry default, see get_active_state_code().
    """

    __tablename__ = "facility_compliance_state"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    state_code: Mapped[str] = mapped_column(String)
    updated_by: Mapped[str] = mapped_column(String, default="unknown")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class FacilitySecuritySettings(Base):
    """
    Facility-wide security policy — currently just whether every operator is required
    to have a PIN configured. Same "always exactly one row, audited, server-side"
    pattern as FacilityComplianceState: this is a fact about how this facility wants to
    operate (every operator picker on shared hardware should require a PIN before
    acting under someone else's name), not a per-browser preference, so changing it
    goes through the same attributed, audit-logged bar as any other compliance-mutating
    action here — see services/security_settings.py.
    """

    __tablename__ = "facility_security_settings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    require_operator_pins: Mapped[bool] = mapped_column(default=False)
    updated_by: Mapped[str] = mapped_column(String, default="unknown")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class MenuSyncStatus(Base):
    """
    The last result of pushing a menu snapshot to the active menu_sync plugin (see
    services/menu_sync_task.py) — persisted, not just kept in-memory (unlike
    services/health.py's per-process task tracker), so the Settings page can show a
    meaningful "last synced" time across restarts, same "always exactly one row"
    pattern as RelayCursor/FacilityComplianceState.
    """

    __tablename__ = "menu_sync_status"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_result: Mapped[dict] = mapped_column(JSON, default=dict)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
