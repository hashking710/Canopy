from sqlalchemy import select

from canopy_agent.compliance_models import FacilityComplianceState, LabTest, Package, PlantBatch
from canopy_agent.seed_compliance import seed_compliance


def test_seed_sets_an_explicit_jurisdiction(db_session):
    seed_compliance(db_session)

    state = db_session.get(FacilityComplianceState, "facility")
    assert state is not None
    assert state.state_code == "CA"


def test_seed_creates_a_solvent_derived_package_with_a_passing_lab_test(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("canopy_agent.seed_compliance.COA_DIR", tmp_path)

    seed_compliance(db_session)

    processed = db_session.execute(select(Package).where(Package.process_method.isnot(None))).scalar_one()
    assert processed.process_method == "BHO Extraction"
    assert processed.source_package_id is not None

    lab_test = db_session.execute(select(LabTest).where(LabTest.package_id == processed.id)).scalar_one()
    assert lab_test.result == "pass"
    assert lab_test.test_type == "residual_solvents"


def test_seed_writes_a_real_readable_coa_pdf_to_disk(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("canopy_agent.seed_compliance.COA_DIR", tmp_path)

    seed_compliance(db_session)

    lab_test = db_session.execute(select(LabTest).where(LabTest.coa_filename.isnot(None))).scalar_one()
    stored_path = tmp_path / lab_test.coa_stored_path
    assert stored_path.exists()
    content = stored_path.read_bytes()
    assert content.startswith(b"%PDF-1.4")
    assert content.rstrip().endswith(b"%%EOF")
    assert b"CERTIFICATE OF ANALYSIS" in content


def test_seed_is_idempotent_and_only_seeds_once(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("canopy_agent.seed_compliance.COA_DIR", tmp_path)

    seed_compliance(db_session)
    seed_compliance(db_session)  # a second call must be a no-op, not duplicate data

    assert db_session.execute(select(PlantBatch)).scalars().all().__len__() == 3
