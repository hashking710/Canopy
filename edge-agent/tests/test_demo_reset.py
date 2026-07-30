from sqlalchemy import select

from canopy_agent import compliance_models  # noqa: F401  # registers compliance tables
from canopy_agent.compliance_models import Operator
from canopy_agent.models import Room
from canopy_agent.services import demo_reset
from canopy_agent.services.demo_reset import reset_demo_data


def test_reset_seeds_a_fresh_dataset_on_an_empty_db(db_session):
    assert db_session.execute(select(Room)).first() is None

    reset_demo_data(db_session)

    rooms = db_session.execute(select(Room)).scalars().all()
    assert len(rooms) > 0


def test_reset_wipes_visitor_changes_and_restores_the_fixed_dataset(db_session):
    reset_demo_data(db_session)
    original_room_ids = {r.id for r in db_session.execute(select(Room)).scalars().all()}

    # Simulate a visitor's tampering: delete a seeded room, add a bogus one.
    victim = db_session.execute(select(Room)).scalars().first()
    db_session.delete(victim)
    db_session.add(Room(id="visitor-junk-room", room_type="greenhouse", path="~/junk", metric_config={}))
    db_session.commit()

    reset_demo_data(db_session)

    reset_room_ids = {r.id for r in db_session.execute(select(Room)).scalars().all()}
    assert reset_room_ids == original_room_ids
    assert "visitor-junk-room" not in reset_room_ids


def test_reset_also_restores_compliance_demo_data(db_session):
    reset_demo_data(db_session)
    assert db_session.execute(select(Operator)).first() is not None


def test_reset_clears_orphaned_coa_uploads_from_disk(db_session, tmp_path, monkeypatch):
    # A visitor's uploaded COA is a real file on disk, not just a DB row — wiping
    # lab_tests alone would leave it there forever with nothing pointing at it, an
    # unbounded disk leak on a demo instance that resets hourly, forever.
    fake_coa_dir = tmp_path / "coa_uploads"
    fake_coa_dir.mkdir()
    (fake_coa_dir / "visitor-upload.pdf").write_bytes(b"%PDF-1.4 fake")
    (fake_coa_dir / "another.pdf").write_bytes(b"%PDF-1.4 also fake")
    monkeypatch.setattr(demo_reset, "COA_DIR", fake_coa_dir)

    reset_demo_data(db_session)

    assert list(fake_coa_dir.iterdir()) == []


def test_reset_does_not_error_when_the_coa_directory_does_not_exist_yet(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(demo_reset, "COA_DIR", tmp_path / "never-created")
    reset_demo_data(db_session)  # must not raise
