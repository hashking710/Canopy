import json
import logging
import uuid
from dataclasses import asdict
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from canopy_agent.compliance_models import (
    AuditLogEntry,
    FacilityComplianceState,
    Harvest,
    HarvestWeightLog,
    LabTest,
    Operator,
    Package,
    Plant,
    PlantBatch,
    PhysicalCount,
    Strain,
    WasteEvent,
)
from canopy_agent.compliance_schemas import (
    CreateHarvestRequest,
    CreateLabTestRequest,
    CreatePlantBatchRequest,
    DestroyPlantRequest,
    FinishHarvestRequest,
    HarvestPlantRequest,
    LogWasteRequest,
    MovePlantRequest,
    PackageHarvestRequest,
    ProcessPackageRequest,
    RecordPhysicalCountRequest,
    SetComplianceStateRequest,
    TagPlantsRequest,
    UpdatePackageStatusRequest,
    WeighHarvestRequest,
)
from canopy_agent.compliance_rules import get_rules
from canopy_agent.compliance_rules.registry import list_states
from canopy_agent.compliance_serialize import model_to_dict
from canopy_agent.compliance_sync.registry import get_compliance_sync
from canopy_agent.deps import get_db
from canopy_agent.models import Room
from canopy_agent.services.audit import record_audit, verify_audit_chain
from canopy_agent.services.coa_storage import CoaUploadError, coa_path, save_coa
from canopy_agent.services.compliance_deadlines import is_waste_overdue, waste_reporting_deadline
from canopy_agent.services.csv_export import rows_to_csv
from canopy_agent.services.facility_state import FACILITY_STATE_ROW_ID, get_active_state_code, set_active_state_code
from canopy_agent.services.operators import get_active_operator, pin_check_failed, require_role
from canopy_agent.services.reconciliation import (
    is_recount_stale,
    latest_physical_counts,
    system_plant_count,
    system_plant_counts,
)

logger = logging.getLogger("canopy_agent.compliance")

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


async def _sync(coro) -> None:
    """A compliance sync failure (once a real one exists — NullComplianceSync never
    raises) must never block local recording, same as the MQTT publisher/adapters."""
    try:
        await coro
    except Exception:
        logger.exception("compliance sync failed; local record was still saved")


def _resolve_operator(db: Session, operator_id: str) -> Operator:
    """Every compliance action is attributed to a real, registered Operator — not a
    free-text string anyone could type any name into (see compliance_models.Operator)
    — and, since operator_id is already mandatory on every mutating call site here,
    this is also the one place that needs to enforce that a 'viewer'-role operator
    can never perform (or witness) a compliance mutation. Read-only endpoints in
    this router never call this function, so nothing here affects list/GET access."""
    operator = get_active_operator(db, operator_id)
    if operator is None:
        raise HTTPException(status_code=404, detail=f"operator '{operator_id}' not found or inactive")
    require_role(operator, "operator")
    return operator


def _validate_strain_id(db: Session, strain_id: str | None) -> None:
    """strain_id is an optional link to the genetics registry (see
    services/menu_data.py) — if one's given, it needs to actually point at a real,
    active strain, or menu sync would silently resolve nothing for it later."""
    if strain_id is None:
        return
    strain = db.get(Strain, strain_id)
    if strain is None or not strain.active:
        raise HTTPException(status_code=404, detail=f"strain '{strain_id}' not found or inactive")


def _require_pin_if_configured(operator: Operator, pin: str | None) -> None:
    if pin_check_failed(operator, pin):
        raise HTTPException(status_code=401, detail=f"PIN required or incorrect for operator '{operator.name}'")


def _resolve_witness(db: Session, witness_operator_id: str | None, actor: Operator) -> str | None:
    if witness_operator_id is None:
        return None
    witness = _resolve_operator(db, witness_operator_id)
    if witness.id == actor.id:
        raise HTTPException(status_code=400, detail="a witness must be a different operator than the one performing the action")
    return witness.name


# ---- Plant batches (immature lots) -----------------------------------------------


@router.post("/plant-batches")
async def create_plant_batch(body: CreatePlantBatchRequest, db: Session = Depends(get_db)) -> dict:
    operator = _resolve_operator(db, body.operator_id)
    _validate_strain_id(db, body.strain_id)
    batch = PlantBatch(
        id=_new_id("batch"),
        name=body.name,
        batch_type=body.batch_type,
        strain=body.strain,
        strain_id=body.strain_id,
        room_id=body.room_id,
        planted_date=body.planted_date,
        untracked_count=body.count,
        tracked_count=0,
        packaged_count=0,
        harvested_count=0,
        destroyed_count=0,
    )
    db.add(batch)
    record_audit(
        db, "plant_batch", batch.id, "created", operator.name, room_id=body.room_id,
        details={"name": body.name, "count": body.count, "strain": body.strain},
    )
    db.commit()
    await _sync(get_compliance_sync().sync_plant_batch_created(model_to_dict(batch)))
    return model_to_dict(batch)


@router.get("/plant-batches")
def list_plant_batches(db: Session = Depends(get_db)) -> list[dict]:
    return [model_to_dict(b) for b in db.execute(select(PlantBatch)).scalars().all()]


@router.post("/plant-batches/{batch_id}/tag-plants")
async def tag_plants(batch_id: str, body: TagPlantsRequest, db: Session = Depends(get_db)) -> dict:
    operator = _resolve_operator(db, body.operator_id)
    batch = db.get(PlantBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="plant batch not found")
    if body.count > batch.untracked_count:
        raise HTTPException(
            status_code=400, detail=f"only {batch.untracked_count} untracked plants remain in this batch"
        )

    room_id = body.room_id or batch.room_id
    today = date.today()
    created: list[Plant] = []
    for _ in range(body.count):
        plant = Plant(
            id=_new_id(f"{batch.name}-tag"),
            batch_id=batch.id,
            strain=batch.strain,
            room_id=room_id,
            growth_phase=body.growth_phase,
            planted_date=batch.planted_date,
            tagged_date=today,
        )
        db.add(plant)
        created.append(plant)
        record_audit(
            db, "plant", plant.id, "tagged", operator.name, room_id=room_id,
            details={"batch_id": batch.id, "growth_phase": body.growth_phase},
        )

    batch.untracked_count -= body.count
    batch.tracked_count += body.count
    record_audit(db, "plant_batch", batch.id, "plants_tagged", operator.name, room_id=room_id, details={"count": body.count})
    db.commit()

    for plant in created:
        await _sync(get_compliance_sync().sync_plant_tagged(model_to_dict(plant)))

    return {"batch": model_to_dict(batch), "plants": [model_to_dict(p) for p in created]}


# ---- Individually tagged plants ---------------------------------------------------


@router.get("/plants")
def list_plants(db: Session = Depends(get_db)) -> list[dict]:
    return [model_to_dict(p) for p in db.execute(select(Plant)).scalars().all()]


@router.post("/plants/{plant_id}/move")
async def move_plant(plant_id: str, body: MovePlantRequest, db: Session = Depends(get_db)) -> dict:
    operator = _resolve_operator(db, body.operator_id)
    plant = db.get(Plant, plant_id)
    if plant is None:
        raise HTTPException(status_code=404, detail="plant not found")

    from_room_id = plant.room_id
    destination_is_local = db.get(Room, body.room_id) is not None
    details = {"from_room_id": from_room_id, "to_room_id": body.room_id}
    if destination_is_local:
        plant.room_id = body.room_id
    else:
        # Not one of this device's rooms — a cross-device move (a second Pi at this
        # site owns that room). This device retires its own copy rather than leaving
        # room_id pointing at a room it has no information about; the "moved" audit
        # entry below is what services/audit_relay.py relays over MQTT, and the room's
        # actual owning device creates its own local Plant record on receipt — carrying
        # enough of the plant's own fields along that the receiving device doesn't have
        # to guess at strain/phase/planted_date for the record it creates.
        plant.status = "transferred"
        details["plant_snapshot"] = {
            "strain": plant.strain,
            "growth_phase": plant.growth_phase,
            "planted_date": plant.planted_date.isoformat(),
            "tagged_date": plant.tagged_date.isoformat(),
            "mother_plant_id": plant.mother_plant_id,
        }
    record_audit(
        db, "plant", plant.id, "moved", operator.name,
        room_id=body.room_id if destination_is_local else from_room_id,
        details=details,
    )
    db.commit()
    await _sync(get_compliance_sync().sync_plant_moved(model_to_dict(plant), from_room_id))
    return model_to_dict(plant)


@router.post("/plants/{plant_id}/destroy")
async def destroy_plant(plant_id: str, body: DestroyPlantRequest, db: Session = Depends(get_db)) -> dict:
    operator = _resolve_operator(db, body.operator_id)
    _require_pin_if_configured(operator, body.pin)
    witness_name = _resolve_witness(db, body.witness_operator_id, operator)

    plant = db.get(Plant, plant_id)
    if plant is None:
        raise HTTPException(status_code=404, detail="plant not found")
    if plant.status != "active":
        raise HTTPException(status_code=400, detail=f"plant is already {plant.status}")

    plant.status = "destroyed"
    waste = WasteEvent(
        source_type="plant",
        source_id=plant.id,
        room_id=plant.room_id,
        waste_type="Plant Material",
        method=body.method,
        material=body.material,
        reason=body.reason,
        weight_g=body.weight_g,
        note=body.note,
        actor=operator.name,
        witnessed_by=witness_name,
    )
    db.add(waste)

    if plant.batch_id:
        batch = db.get(PlantBatch, plant.batch_id)
        if batch is not None:
            batch.tracked_count = max(0, batch.tracked_count - 1)
            batch.destroyed_count += 1

    record_audit(
        db, "plant", plant.id, "destroyed", operator.name, room_id=plant.room_id,
        details={"weight_g": body.weight_g, "reason": body.reason, "method": body.method, "witnessed_by": witness_name},
    )
    db.commit()

    waste_dict = model_to_dict(waste)
    await _sync(get_compliance_sync().sync_plant_destroyed(model_to_dict(plant), waste_dict))
    await _sync(get_compliance_sync().sync_waste_event(waste_dict))
    return {"plant": model_to_dict(plant), "waste_event": waste_dict}


@router.post("/plants/{plant_id}/harvest")
async def harvest_plant(plant_id: str, body: HarvestPlantRequest, db: Session = Depends(get_db)) -> dict:
    operator = _resolve_operator(db, body.operator_id)
    plant = db.get(Plant, plant_id)
    if plant is None:
        raise HTTPException(status_code=404, detail="plant not found")
    if plant.status != "active":
        raise HTTPException(status_code=400, detail=f"plant is already {plant.status}")
    harvest = db.get(Harvest, body.harvest_id)
    if harvest is None:
        raise HTTPException(status_code=404, detail="harvest not found")

    plant.status = "harvested"
    harvest.wet_weight_g += body.weight_g
    db.add(
        HarvestWeightLog(
            harvest_id=harvest.id, stage="wet", weight_g=body.weight_g,
            room_id=harvest.source_room_id, actor=operator.name,
        )
    )

    if plant.batch_id:
        batch = db.get(PlantBatch, plant.batch_id)
        if batch is not None:
            batch.tracked_count = max(0, batch.tracked_count - 1)
            batch.harvested_count += 1

    record_audit(
        db, "plant", plant.id, "harvested", operator.name, room_id=plant.room_id,
        details={"harvest_id": harvest.id, "weight_g": body.weight_g},
    )
    db.commit()
    return {"plant": model_to_dict(plant), "harvest": model_to_dict(harvest)}


# ---- Harvests -----------------------------------------------------------------------


@router.post("/harvests")
async def create_harvest(body: CreateHarvestRequest, db: Session = Depends(get_db)) -> dict:
    operator = _resolve_operator(db, body.operator_id)
    _validate_strain_id(db, body.strain_id)
    existing = db.execute(select(Harvest).where(Harvest.name == body.name)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=400, detail=f"harvest name '{body.name}' already exists — METRC requires unique harvest names"
        )

    harvest = Harvest(
        id=_new_id("harvest"),
        name=body.name,
        strain=body.strain,
        strain_id=body.strain_id,
        source_room_id=body.source_room_id,
        drying_room_id=body.drying_room_id,
        wet_weight_g=0.0,
    )
    db.add(harvest)
    db.flush()  # populate harvest.started_at's column default before snapshotting it below
    record_audit(
        db, "harvest", harvest.id, "created", operator.name, room_id=body.source_room_id,
        # harvest_snapshot lets a *different* device at the same site reconstruct this
        # harvest locally from the relayed audit event alone (see audit_relay.py's
        # process_relay_event) — the same "snapshot in the audit details" idiom
        # plant moves already use, so any device's plants can be harvested into this
        # harvest, not just the one that happened to create it.
        details={
            "name": body.name, "strain": body.strain,
            "harvest_snapshot": {
                "name": body.name, "strain": body.strain,
                "source_room_id": body.source_room_id, "drying_room_id": body.drying_room_id,
                "wet_weight_g": harvest.wet_weight_g, "started_at": harvest.started_at.isoformat(),
            },
        },
    )
    db.commit()
    await _sync(get_compliance_sync().sync_harvest_created(model_to_dict(harvest)))
    return model_to_dict(harvest)


@router.get("/harvests")
def list_harvests(db: Session = Depends(get_db)) -> list[dict]:
    return [model_to_dict(h) for h in db.execute(select(Harvest)).scalars().all()]


@router.post("/harvests/{harvest_id}/weigh")
def weigh_harvest(harvest_id: str, body: WeighHarvestRequest, db: Session = Depends(get_db)) -> dict:
    operator = _resolve_operator(db, body.operator_id)
    harvest = db.get(Harvest, harvest_id)
    if harvest is None:
        raise HTTPException(status_code=404, detail="harvest not found")

    log = HarvestWeightLog(
        harvest_id=harvest.id, stage=body.stage, weight_g=body.weight_g, room_id=body.room_id, actor=operator.name
    )
    db.add(log)
    record_audit(
        db, "harvest", harvest.id, "weighed", operator.name, room_id=body.room_id,
        details={"stage": body.stage, "weight_g": body.weight_g},
    )
    db.commit()
    return model_to_dict(log)


@router.get("/harvests/{harvest_id}/weight-logs")
def get_harvest_weight_logs(harvest_id: str, db: Session = Depends(get_db)) -> list[dict]:
    logs = (
        db.execute(select(HarvestWeightLog).where(HarvestWeightLog.harvest_id == harvest_id).order_by(HarvestWeightLog.recorded_at))
        .scalars()
        .all()
    )
    return [model_to_dict(log) for log in logs]


@router.post("/harvests/{harvest_id}/finish")
def finish_harvest(harvest_id: str, body: FinishHarvestRequest, db: Session = Depends(get_db)) -> dict:
    operator = _resolve_operator(db, body.operator_id)
    harvest = db.get(Harvest, harvest_id)
    if harvest is None:
        raise HTTPException(status_code=404, detail="harvest not found")

    harvest.status = "finished"
    harvest.finished_at = datetime.now(timezone.utc)
    record_audit(db, "harvest", harvest.id, "finished", operator.name)
    db.commit()
    return model_to_dict(harvest)


@router.post("/harvests/{harvest_id}/package")
async def package_harvest(harvest_id: str, body: PackageHarvestRequest, db: Session = Depends(get_db)) -> dict:
    operator = _resolve_operator(db, body.operator_id)
    harvest = db.get(Harvest, harvest_id)
    if harvest is None:
        raise HTTPException(status_code=404, detail="harvest not found")

    package = Package(
        id=body.tag or _new_id("pkg"),
        harvest_id=harvest.id,
        item_name=body.item_name,
        weight_g=body.weight_g,
        room_id=body.room_id,
        is_production_batch=body.is_production_batch,
        is_donation=body.is_donation,
    )
    db.add(package)
    record_audit(
        db, "package", package.id, "created", operator.name, room_id=body.room_id,
        # package_snapshot mirrors harvest_snapshot's role in create_harvest — lets a
        # different device at the same site reconstruct this package locally from the
        # relayed event alone (see audit_relay.py's _process_package_created). Only
        # covers a harvest-sourced package, not a processed derivative one (those use
        # a different audit action, "processed" — not relayed today, see
        # docs/architecture.md).
        details={
            "harvest_id": harvest.id, "item_name": body.item_name, "weight_g": body.weight_g,
            "package_snapshot": {
                "harvest_id": harvest.id, "item_name": body.item_name, "weight_g": body.weight_g,
                "room_id": body.room_id, "is_production_batch": body.is_production_batch, "is_donation": body.is_donation,
            },
        },
    )
    db.commit()
    await _sync(get_compliance_sync().sync_package_created(model_to_dict(package)))
    return model_to_dict(package)


@router.get("/packages")
def list_packages(db: Session = Depends(get_db)) -> list[dict]:
    return [model_to_dict(p) for p in db.execute(select(Package)).scalars().all()]


_PACKAGE_STATUSES = {"active", "sold", "destroyed", "transferred", "processed"}
# "active" is the only non-terminal status — once a package is sold, destroyed,
# transferred, or fully processed, that's final; it physically left the facility, was
# destroyed, or was consumed into another package, and status can't un-happen that.
_TERMINAL_PACKAGE_STATUSES = _PACKAGE_STATUSES - {"active"}


@router.post("/packages/{package_id}/update-status")
def update_package_status(package_id: str, body: UpdatePackageStatusRequest, db: Session = Depends(get_db)) -> dict:
    if body.status not in _PACKAGE_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(_PACKAGE_STATUSES)}")
    operator = _resolve_operator(db, body.operator_id)
    package = db.get(Package, package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="package not found")
    if package.status in _TERMINAL_PACKAGE_STATUSES:
        raise HTTPException(
            status_code=400, detail=f"package is already '{package.status}', a final status — it can't be changed again"
        )

    previous_status = package.status
    package.status = body.status
    record_audit(
        db, "package", package.id, "status_changed", operator.name, room_id=package.room_id,
        details={"from": previous_status, "to": body.status},
    )
    db.commit()
    return model_to_dict(package)


# ---- Package processing (manufacturing/extraction chains: BHO, CO2, distillate, etc.) ----


@router.post("/packages/{package_id}/process")
async def process_package(package_id: str, body: ProcessPackageRequest, db: Session = Depends(get_db)) -> dict:
    """Turn a source package into a new derivative package — one step of a
    manufacturing chain (e.g. trim -> BHO crude -> winterized oil -> distillate).
    The source package is left as-is (still "active" unless someone explicitly marks
    it "processed"/"destroyed" via update-status) since one source can legitimately
    yield more than one downstream output (e.g. crude oil -> distillate + terpenes)."""
    operator = _resolve_operator(db, body.operator_id)
    source = db.get(Package, package_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source package not found")

    # Mass conservation: a real extraction/refinement step never yields more material
    # than went into it. Checked cumulatively (not just against this one call) since
    # a source is allowed to feed *multiple* downstream outputs (e.g. crude oil ->
    # distillate + terpenes) — the sum of everything already pulled from this source
    # plus this new request must still fit within what the source actually weighs.
    already_processed = db.execute(
        select(func.coalesce(func.sum(Package.weight_g), 0.0)).where(Package.source_package_id == source.id)
    ).scalar_one()
    remaining = source.weight_g - already_processed
    if body.weight_g > remaining:
        raise HTTPException(
            status_code=400,
            detail=(
                f"output weight ({body.weight_g}g) exceeds the source package's remaining unprocessed weight "
                f"({remaining}g of {source.weight_g}g — {already_processed}g already pulled into other packages)"
            ),
        )

    package = Package(
        id=body.tag or _new_id("pkg"),
        source_package_id=source.id,
        process_method=body.process_method,
        process_yield_pct=(body.weight_g / source.weight_g * 100) if source.weight_g else None,
        item_name=body.item_name,
        weight_g=body.weight_g,
        room_id=body.room_id,
        is_production_batch=body.is_production_batch,
        is_donation=body.is_donation,
    )
    db.add(package)
    record_audit(
        db, "package", package.id, "processed", operator.name, room_id=body.room_id,
        details={
            "source_package_id": source.id, "process_method": body.process_method,
            "item_name": body.item_name, "weight_g": body.weight_g,
        },
    )
    db.commit()
    await _sync(get_compliance_sync().sync_package_created(model_to_dict(package)))
    return model_to_dict(package)


@router.get("/packages/{package_id}/lineage")
def get_package_lineage(package_id: str, db: Session = Depends(get_db)) -> list[dict]:
    """This package and every ancestor package it was processed from, root (the
    original harvest-packaged material) first — walks source_package_id back until
    it hits a package with none. Guards against a cycle (shouldn't be reachable
    through the API, since a package can only name an already-existing package as
    its source, but a corrupted/hand-edited DB shouldn't be able to hang this)."""
    chain: list[Package] = []
    seen: set[str] = set()
    current = db.get(Package, package_id)
    if current is None:
        raise HTTPException(status_code=404, detail="package not found")
    while current is not None and current.id not in seen:
        chain.append(current)
        seen.add(current.id)
        current = db.get(Package, current.source_package_id) if current.source_package_id else None
    chain.reverse()
    return [model_to_dict(p) for p in chain]


# ---- Lab tests (potency/contaminant/residual-solvent results against a package) ----


@router.post("/packages/{package_id}/lab-tests")
def create_lab_test(package_id: str, body: CreateLabTestRequest, db: Session = Depends(get_db)) -> dict:
    operator = _resolve_operator(db, body.operator_id)
    package = db.get(Package, package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="package not found")
    if body.result not in ("pass", "fail", "pending"):
        raise HTTPException(status_code=400, detail="result must be 'pass', 'fail', or 'pending'")

    test = LabTest(
        id=_new_id("labtest"),
        package_id=package.id,
        lab_name=body.lab_name,
        test_type=body.test_type,
        result=body.result,
        thc_pct=body.thc_pct,
        cbd_pct=body.cbd_pct,
        notes=body.notes,
        tested_at=body.tested_at,
        recorded_by=operator.name,
    )
    db.add(test)
    record_audit(
        db, "package", package.id, "lab_test_recorded", operator.name, room_id=package.room_id,
        details={"test_type": body.test_type, "result": body.result, "lab_name": body.lab_name},
    )
    db.commit()
    return model_to_dict(test)


@router.get("/packages/{package_id}/lab-tests")
def list_package_lab_tests(package_id: str, db: Session = Depends(get_db)) -> list[dict]:
    # tested_at is a plain date (no time component), so two same-day tests need
    # recorded_at (a real timestamp) as a tiebreaker — otherwise "most recent test"
    # is ambiguous exactly when it matters most: a same-day retest superseding an
    # earlier failing result.
    tests = (
        db.execute(
            select(LabTest)
            .where(LabTest.package_id == package_id)
            .order_by(LabTest.tested_at.desc(), LabTest.recorded_at.desc())
        )
        .scalars()
        .all()
    )
    return [model_to_dict(t) for t in tests]


@router.get("/lab-tests")
def list_lab_tests(result: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    query = select(LabTest).order_by(LabTest.tested_at.desc(), LabTest.recorded_at.desc())
    if result:
        query = query.where(LabTest.result == result)
    return [model_to_dict(t) for t in db.execute(query).scalars().all()]


@router.post("/lab-tests/{test_id}/coa")
async def upload_lab_test_coa(
    test_id: str, operator_id: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)
) -> dict:
    """Attaches the lab's own COA (PDF or scan) to an existing test record as-is —
    kept on file for inspections, never parsed for its data (see coa_storage.py)."""
    operator = _resolve_operator(db, operator_id)
    test = db.get(LabTest, test_id)
    if test is None:
        raise HTTPException(status_code=404, detail="lab test not found")
    try:
        stored_path, filename = await save_coa(file)
    except CoaUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    test.coa_stored_path = stored_path
    test.coa_filename = filename
    package = db.get(Package, test.package_id)
    record_audit(
        db, "package", test.package_id, "coa_attached", operator.name,
        room_id=package.room_id if package else None,
        details={"lab_test_id": test.id, "filename": filename},
    )
    db.commit()
    return model_to_dict(test)


@router.get("/lab-tests/{test_id}/coa")
def download_lab_test_coa(test_id: str, db: Session = Depends(get_db)) -> FileResponse:
    test = db.get(LabTest, test_id)
    if test is None or not test.coa_stored_path:
        raise HTTPException(status_code=404, detail="no COA attached to this test")
    try:
        path = coa_path(test.coa_stored_path)
    except CoaUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    if not path.exists():
        raise HTTPException(status_code=404, detail="COA file is missing from storage")
    return FileResponse(path, filename=test.coa_filename or path.name)


# ---- Waste (batch/harvest/package sources; plant waste happens via /plants/{id}/destroy) -----


@router.post("/waste")
async def log_waste(body: LogWasteRequest, db: Session = Depends(get_db)) -> dict:
    operator = _resolve_operator(db, body.operator_id)
    _require_pin_if_configured(operator, body.pin)
    witness_name = _resolve_witness(db, body.witness_operator_id, operator)

    occurred_at = body.occurred_at or datetime.now(timezone.utc)
    waste = WasteEvent(
        source_type=body.source_type,
        source_id=body.source_id,
        room_id=body.room_id,
        waste_type=body.waste_type,
        method=body.method,
        material=body.material,
        reason=body.reason,
        weight_g=body.weight_g,
        note=body.note,
        actor=operator.name,
        witnessed_by=witness_name,
        occurred_at=occurred_at,
    )
    db.add(waste)

    if body.source_type == "plant_batch":
        batch = db.get(PlantBatch, body.source_id)
        if batch is None:
            raise HTTPException(status_code=404, detail="plant batch not found")
        batch.untracked_count = max(0, batch.untracked_count - body.plant_count)
        batch.destroyed_count += body.plant_count

    record_audit(
        db, body.source_type, body.source_id, "waste_logged", operator.name, room_id=body.room_id,
        details={"weight_g": body.weight_g, "waste_type": body.waste_type, "witnessed_by": witness_name},
    )
    db.commit()
    await _sync(get_compliance_sync().sync_waste_event(model_to_dict(waste)))
    return model_to_dict(waste)


@router.get("/waste-events")
def list_waste_events(overdue_only: bool = False, db: Session = Depends(get_db)) -> list[dict]:
    state_code = get_active_state_code(db)
    events = db.execute(select(WasteEvent).order_by(WasteEvent.occurred_at.desc())).scalars().all()
    out = []
    for event in events:
        overdue = is_waste_overdue(event.occurred_at, event.reported_at, state_code=state_code)
        # overdue is None for states whose deadline shape isn't a computable "report by
        # X" date (e.g. a pre-destruction notice requirement) — don't claim those are
        # overdue just because they aren't definitively True.
        if overdue_only and overdue is not True:
            continue
        deadline = waste_reporting_deadline(event.occurred_at, state_code=state_code)
        payload = model_to_dict(event)
        payload["reporting_deadline"] = deadline.isoformat() if deadline else None
        payload["overdue"] = overdue
        out.append(payload)
    return out


@router.post("/waste-events/{waste_event_id}/mark-reported")
def mark_waste_reported(waste_event_id: int, operator_id: str, db: Session = Depends(get_db)) -> dict:
    operator = _resolve_operator(db, operator_id)
    event = db.get(WasteEvent, waste_event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="waste event not found")
    event.reported_at = datetime.now(timezone.utc)
    record_audit(db, "waste_event", str(event.id), "marked_reported", operator.name, room_id=event.room_id)
    db.commit()
    return model_to_dict(event)


# ---- Audit trail --------------------------------------------------------------------


@router.get("/audit-log")
def get_audit_log(
    entity_type: str | None = None,
    entity_id: str | None = None,
    room_id: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[dict]:
    query = select(AuditLogEntry).order_by(AuditLogEntry.occurred_at.desc()).limit(min(limit, 500))
    if entity_type:
        query = query.where(AuditLogEntry.entity_type == entity_type)
    if entity_id:
        query = query.where(AuditLogEntry.entity_id == entity_id)
    if room_id:
        query = query.where(AuditLogEntry.room_id == room_id)
    return [model_to_dict(e) for e in db.execute(query).scalars().all()]


@router.get("/audit-log/verify")
def verify_audit_log(db: Session = Depends(get_db)) -> dict:
    broken_entry_ids = verify_audit_chain(db)
    return {"intact": not broken_entry_ids, "broken_entry_ids": broken_entry_ids}


@router.get("/state-rules")
def get_active_state_rules(db: Session = Depends(get_db)) -> dict:
    """
    Which state's compliance ruleset this facility is using, and how much of it is
    actually verified vs. best-effort — surfaced so this isn't a silent assumption.
    See compliance_rules/ for full sourcing per state. `explicitly_set` distinguishes
    an operator's deliberate choice (POST below) from CANOPY_COMPLIANCE_STATE / the
    registry default, which a facility that's never touched this endpoint is still
    silently relying on.
    """
    return {
        "active": asdict(get_rules(get_active_state_code(db))),
        "explicitly_set": db.get(FacilityComplianceState, FACILITY_STATE_ROW_ID) is not None,
        "available": [asdict(r) for r in list_states()],
    }


@router.post("/state-rules")
def set_active_state_rules(body: SetComplianceStateRequest, db: Session = Depends(get_db)) -> dict:
    """
    Changes which state's compliance ruleset this facility operates under — a fact
    about the facility's actual legal jurisdiction (which deadlines/testing
    requirements apply), not a per-browser display preference. Attributed to a real
    operator and audit-logged, same bar as any other compliance-mutating action here.
    """
    operator = _resolve_operator(db, body.operator_id)
    previous_code = get_active_state_code(db)
    try:
        set_active_state_code(db, body.state_code, operator.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    record_audit(
        db, "facility", FACILITY_STATE_ROW_ID, "compliance_state_changed", operator.name,
        details={"from": previous_code, "to": body.state_code.upper()},
    )
    db.commit()
    return {
        "active": asdict(get_rules(get_active_state_code(db))),
        "explicitly_set": True,
        "available": [asdict(r) for r in list_states()],
    }


# ---- Export (for inspections / audits — nothing here changes state) -----------------


def _csv_response(csv_data: str, filename: str) -> StreamingResponse:
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/audit-log")
def export_audit_log_csv(
    start: datetime | None = None, end: datetime | None = None, db: Session = Depends(get_db)
) -> StreamingResponse:
    query = select(AuditLogEntry).order_by(AuditLogEntry.occurred_at)
    if start:
        query = query.where(AuditLogEntry.occurred_at >= start)
    if end:
        query = query.where(AuditLogEntry.occurred_at <= end)

    rows = [
        {
            "occurred_at": e.occurred_at.isoformat(),
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "action": e.action,
            "actor": e.actor,
            "room_id": e.room_id or "",
            "details": json.dumps(e.details),
        }
        for e in db.execute(query).scalars().all()
    ]
    return _csv_response(rows_to_csv(rows), "canopy-audit-log.csv")


@router.get("/export/waste-events")
def export_waste_events_csv(
    start: datetime | None = None, end: datetime | None = None, db: Session = Depends(get_db)
) -> StreamingResponse:
    query = select(WasteEvent).order_by(WasteEvent.occurred_at)
    if start:
        query = query.where(WasteEvent.occurred_at >= start)
    if end:
        query = query.where(WasteEvent.occurred_at <= end)

    rows = [
        {
            "occurred_at": e.occurred_at.isoformat(),
            "room_id": e.room_id,
            "source_type": e.source_type,
            "source_id": e.source_id,
            "waste_type": e.waste_type,
            "method": e.method or "",
            "material": e.material or "",
            "reason": e.reason or "",
            "weight_g": e.weight_g,
            "actor": e.actor,
            "witnessed_by": e.witnessed_by or "",
            "reported_at": e.reported_at.isoformat() if e.reported_at else "",
        }
        for e in db.execute(query).scalars().all()
    ]
    return _csv_response(rows_to_csv(rows), "canopy-waste-events.csv")


# ---- Reconciliation -------------------------------------------------------------------


@router.get("/reconciliation")
def get_reconciliation(db: Session = Depends(get_db)) -> list[dict]:
    room_ids = set(
        db.execute(select(Plant.room_id).where(Plant.status == "active")).scalars().all()
    ) | set(
        db.execute(select(PlantBatch.room_id).where(PlantBatch.status == "active")).scalars().all()
    )

    cadence_days = get_rules(get_active_state_code(db)).reconciliation_cadence_days

    sorted_room_ids = sorted(room_ids)
    system_counts = system_plant_counts(db, sorted_room_ids)
    last_counts = latest_physical_counts(db, sorted_room_ids)

    out = []
    for room_id in sorted_room_ids:
        system_count = system_counts.get(room_id, 0)
        last_count = last_counts.get(room_id)
        discrepancy = (last_count.counted_value - system_count) if last_count else None
        stale = last_count is not None and is_recount_stale(last_count.counted_at, cadence_days)

        out.append(
            {
                "room_id": room_id,
                "system_count": system_count,
                "last_physical_count": last_count.counted_value if last_count else None,
                "last_counted_at": last_count.counted_at.isoformat() if last_count else None,
                "discrepancy": discrepancy,
                "needs_recount": last_count is None or discrepancy != 0 or stale,
                "stale": stale,
            }
        )
    return out


@router.post("/physical-counts")
def record_physical_count(body: RecordPhysicalCountRequest, db: Session = Depends(get_db)) -> dict:
    operator = _resolve_operator(db, body.operator_id)
    system_count = system_plant_count(db, body.room_id)
    count = PhysicalCount(
        room_id=body.room_id,
        counted_value=body.counted_value,
        system_value_at_time=system_count,
        counted_by=operator.name,
        note=body.note,
    )
    db.add(count)
    record_audit(
        db, "room", body.room_id, "physical_count", operator.name, room_id=body.room_id,
        details={"counted_value": body.counted_value, "system_value_at_time": system_count},
    )
    db.commit()
    payload = model_to_dict(count)
    payload["discrepancy"] = count.discrepancy
    return payload
