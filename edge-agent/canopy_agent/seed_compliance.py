import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from canopy_agent.compliance_models import (
    Harvest,
    HarvestWeightLog,
    LabTest,
    Operator,
    Package,
    PhysicalCount,
    Plant,
    PlantBatch,
    WasteEvent,
)
from canopy_agent.services.audit import record_audit
from canopy_agent.services.coa_storage import COA_DIR
from canopy_agent.services.facility_state import set_active_state_code
from canopy_agent.services.operators import set_pin


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _make_demo_coa_pdf(lines: list[tuple[int, str]]) -> bytes:
    """A genuinely valid, real single-page PDF — hand-built with computed byte
    offsets (not just '%PDF-1.4' + garbage) so a demo visitor who clicks "view COA"
    and opens the download in a real PDF viewer sees an actual readable document, not
    a broken file. No new dependency for something this small; see coa_storage.py's
    docstring on why COAs are never parsed, only stored — this generator exists
    purely to make the *seeded* demo data self-consistent (a lab test that already
    has a real attached document), not anything the app does at runtime."""
    objs = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    stream_parts = []
    y = 740
    for size, text in lines:
        escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        stream_parts.append(f"BT /F1 {size} Tf 72 {y} Td ({escaped}) Tj ET")
        y -= int(size * 1.6) + 6
    stream = "\n".join(stream_parts).encode("latin-1")
    objs.append(b"<</Length " + str(len(stream)).encode() + b">>\nstream\n" + stream + b"\nendstream")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj".encode() + body + b"endobj\n"
    xref_offset = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += b"trailer<</Size " + str(len(objs) + 1).encode() + b"/Root 1 0 R>>\n"
    out += b"startxref\n" + str(xref_offset).encode() + b"\n%%EOF"
    return bytes(out)


def seed_compliance(db: Session) -> None:
    if db.execute(select(PlantBatch.id)).first() is not None:
        return

    today = date.today()
    now = datetime.now(timezone.utc)

    # A couple of registered operators so the compliance forms are usable out of the
    # box. Demo PIN only — real deployments set their own via POST /api/operators.
    alex = Operator(id=_id("op"), name="Alex Rivera")
    set_pin(alex, "1234")
    jordan = Operator(id=_id("op"), name="Jordan Lee")
    db.add(alex)
    db.add(jordan)

    # --- mother room: 13 individually tagged, vegetative mother plants ---
    mother_batch = PlantBatch(
        id=_id("batch"), name="WSP-2026-Seed-001", batch_type="Seed", strain="Wilson x Sour Papaya",
        room_id="mother-room", planted_date=today - timedelta(days=131),
        # explicit zeros: SQLAlchemy's mapped_column(default=0) only applies at flush
        # time, and this object gets mutated (destroyed_count += 1) before its first
        # flush below, so relying on the column default here would still be None.
        untracked_count=0, tracked_count=13, packaged_count=0, harvested_count=0, destroyed_count=0,
    )
    db.add(mother_batch)
    record_audit(
        db, "plant_batch", mother_batch.id, "created", "seed", room_id="mother-room",
        details={"name": mother_batch.name, "count": 13},
    )

    mother_plants = []
    for _ in range(13):
        plant = Plant(
            id=_id("WSP-tag"), batch_id=mother_batch.id, strain=mother_batch.strain, room_id="mother-room",
            growth_phase="Vegetative", planted_date=mother_batch.planted_date, tagged_date=today - timedelta(days=72),
        )
        db.add(plant)
        mother_plants.append(plant)
        record_audit(
            db, "plant", plant.id, "tagged", "seed", room_id="mother-room",
            details={"batch_id": mother_batch.id, "growth_phase": "Vegetative"},
        )

    # One mother line turned out male and was culled — a real METRC waste reason.
    # Dated 6 days ago so the 3-business-day reporting deadline has already passed,
    # demonstrating the overdue flag with real data rather than an empty list.
    male_plant = mother_plants[0]
    male_plant.status = "destroyed"
    mother_batch.tracked_count -= 1
    mother_batch.destroyed_count += 1
    db.add(
        WasteEvent(
            source_type="plant", source_id=male_plant.id, room_id="mother-room", waste_type="Plant Material",
            method="Compost", material="Soil", reason="Male Plants", weight_g=180.0,
            note="identified during veg, culled", actor="seed", occurred_at=now - timedelta(days=6),
        )
    )
    record_audit(
        db, "plant", male_plant.id, "destroyed", "seed", room_id="mother-room",
        details={"weight_g": 180.0, "reason": "Male Plants"},
    )

    # --- clone room: 35-count immature clone lot, not yet moved to canopy ---
    clone_batch = PlantBatch(
        id=_id("batch"), name="OREOZ-2026-Clone-014", batch_type="Clone", strain="Oreoz",
        room_id="clone-room", planted_date=today - timedelta(days=14), untracked_count=35, tracked_count=0,
    )
    db.add(clone_batch)
    record_audit(
        db, "plant_batch", clone_batch.id, "created", "seed", room_id="clone-room",
        details={"name": clone_batch.name, "count": 35},
    )

    # --- greenhouse B: 28-count immature seedling lot ---
    jb_batch = PlantBatch(
        id=_id("batch"), name="JB-2026-Seed-003", batch_type="Seed", strain="Jelly Breath",
        room_id="greenhouse-b", planted_date=today - timedelta(days=11), untracked_count=28, tracked_count=0,
    )
    db.add(jb_batch)
    record_audit(
        db, "plant_batch", jb_batch.id, "created", "seed", room_id="greenhouse-b",
        details={"name": jb_batch.name, "count": 28},
    )

    # --- greenhouse A: 40 individually tagged flowering plants (Day 12 of flower) ---
    for _ in range(40):
        plant = Plant(
            id=_id("GMO-tag"), batch_id=None, strain="GMO", room_id="greenhouse-a",
            growth_phase="Flowering", planted_date=today - timedelta(days=60), tagged_date=today - timedelta(days=12),
        )
        db.add(plant)
        record_audit(
            db, "plant", plant.id, "tagged", "seed", room_id="greenhouse-a",
            details={"growth_phase": "Flowering"},
        )

    # A prior harvest's lineage feeds the cold-room / dry-cure / press / vault cards.
    harvest = Harvest(
        id=_id("harvest"), name="GMO-2026-06-20", strain="GMO", source_room_id="greenhouse-a",
        drying_room_id="dry-cure", wet_weight_g=4180.0, status="active", started_at=now - timedelta(days=18),
    )
    db.add(harvest)
    record_audit(
        db, "harvest", harvest.id, "created", "seed", room_id="greenhouse-a",
        details={"name": harvest.name, "strain": "GMO"},
    )
    db.add(
        HarvestWeightLog(
            harvest_id=harvest.id, stage="wet", weight_g=4180.0, room_id="greenhouse-a",
            recorded_at=now - timedelta(days=18), actor="seed",
        )
    )
    db.add(
        HarvestWeightLog(
            harvest_id=harvest.id, stage="dry", weight_g=3674.0, room_id="dry-cure",
            recorded_at=now - timedelta(days=3), actor="seed",
        )
    )
    db.add(
        WasteEvent(
            source_type="harvest", source_id=harvest.id, room_id="dry-cure", waste_type="Fibrous",
            weight_g=210.0, note="stem/stalk trim during dry", actor="seed", occurred_at=now - timedelta(days=2),
        )
    )
    record_audit(
        db, "harvest", harvest.id, "waste_logged", "seed", room_id="dry-cure",
        details={"weight_g": 210.0, "waste_type": "Fibrous"},
    )

    package = Package(
        id=_id("pkg"), harvest_id=harvest.id, item_name="GMO Live Rosin", weight_g=106.0, room_id="vault",
        is_production_batch=True, created_at=now - timedelta(hours=6),
    )
    db.add(package)
    record_audit(
        db, "package", package.id, "created", "seed", room_id="vault",
        details={"harvest_id": harvest.id, "item_name": "GMO Live Rosin", "weight_g": 106.0},
    )

    # A solvent-extraction chain (trim -> BHO crude) with a passing lab result and a
    # real attached COA — so the compliance flagging (solvent extracts need a passing
    # test on file before sale) and the COA-upload feature both have something to show
    # out of the box, not just an empty "no lab tests recorded yet" state.
    trim_package = Package(
        id=_id("pkg"), harvest_id=harvest.id, item_name="GMO Trim", weight_g=850.0, room_id="dry-cure",
        created_at=now - timedelta(hours=8),
    )
    db.add(trim_package)
    record_audit(
        db, "package", trim_package.id, "created", "seed", room_id="dry-cure",
        details={"harvest_id": harvest.id, "item_name": "GMO Trim", "weight_g": 850.0},
    )

    bho_crude = Package(
        id=_id("pkg"), source_package_id=trim_package.id, process_method="BHO Extraction",
        process_yield_pct=127.5 / 850.0 * 100, item_name="GMO BHO Crude", weight_g=127.5, room_id="press",
        created_at=now - timedelta(hours=5),
    )
    db.add(bho_crude)
    record_audit(
        db, "package", bho_crude.id, "processed", "seed", room_id="press",
        details={
            "source_package_id": trim_package.id, "process_method": "BHO Extraction",
            "item_name": "GMO BHO Crude", "weight_g": 127.5,
        },
    )

    coa_stored_name = f"{uuid.uuid4().hex}.pdf"
    coa_filename = "gmo-bho-crude-residual-solvents.pdf"
    tested_at = (now - timedelta(hours=4)).date()
    coa_pdf = _make_demo_coa_pdf(
        [
            (18, "CERTIFICATE OF ANALYSIS"),
            (11, "Canopy Analytics Lab (demo data)"),
            (10, f"Sample: {bho_crude.item_name}"),
            (10, f"Package ID: {bho_crude.id}"),
            (10, "Test type: Residual Solvents"),
            (10, "Result: PASS"),
            (10, f"Tested: {tested_at.isoformat()}"),
        ]
    )
    COA_DIR.mkdir(parents=True, exist_ok=True)
    (COA_DIR / coa_stored_name).write_bytes(coa_pdf)

    lab_test = LabTest(
        id=_id("labtest"), package_id=bho_crude.id, lab_name="Canopy Analytics Lab",
        test_type="residual_solvents", result="pass", notes="Demo data", tested_at=tested_at,
        recorded_at=now - timedelta(hours=4), recorded_by="seed",
        coa_filename=coa_filename, coa_stored_path=coa_stored_name,
    )
    db.add(lab_test)
    record_audit(
        db, "package", bho_crude.id, "lab_test_recorded", "seed", room_id="press",
        details={"test_type": "residual_solvents", "result": "pass", "lab_name": "Canopy Analytics Lab"},
    )
    record_audit(
        db, "package", bho_crude.id, "coa_attached", "seed", room_id="press",
        details={"lab_test_id": lab_test.id, "filename": coa_filename},
    )

    # A real, explicit jurisdiction — otherwise the retail-compliance and deadline
    # panels show "not yet explicitly set" instead of actual researched data on a
    # fresh demo/try-it-out instance. California has this project's most thoroughly
    # sourced ruleset, cultivation and retail alike.
    set_active_state_code(db, "CA", "seed")

    # A recent, clean physical recount for greenhouse-a (matches system count exactly)
    # so reconciliation shows both a clean room and rooms still needing a first count.
    db.add(
        PhysicalCount(
            room_id="greenhouse-a", counted_value=40, system_value_at_time=40,
            counted_by="seed", counted_at=now - timedelta(hours=20), note="weekly recount",
        )
    )
    record_audit(
        db, "room", "greenhouse-a", "physical_count", "seed", room_id="greenhouse-a",
        details={"counted_value": 40, "system_value_at_time": 40},
    )

    db.commit()
