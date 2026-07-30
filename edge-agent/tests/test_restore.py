import sqlite3
import tarfile

import pytest

from canopy_agent.restore import restore_backup
from canopy_agent.services.backup import run_backup


def _make_sqlite_db(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE rooms (id TEXT)")
    conn.execute("INSERT INTO rooms VALUES ('greenhouse-a')")
    conn.execute("INSERT INTO rooms VALUES ('greenhouse-b')")
    conn.commit()
    conn.close()


def test_restore_round_trips_the_database_and_coa_uploads(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_sqlite_db(source_dir / "canopy.db")
    coa_dir = source_dir / "coa_uploads"
    coa_dir.mkdir()
    (coa_dir / "report.pdf").write_bytes(b"%PDF-1.4 real coa contents")
    backup_dir = tmp_path / "backups"

    result = run_backup(db_path=source_dir / "canopy.db", coa_dir=coa_dir, backup_dir=backup_dir)

    restore_target = tmp_path / "restored"
    restore_backup(result.path, data_dir=restore_target)

    conn = sqlite3.connect(restore_target / "canopy.db")
    rooms = conn.execute("SELECT id FROM rooms ORDER BY id").fetchall()
    conn.close()
    assert rooms == [("greenhouse-a",), ("greenhouse-b",)]

    assert (restore_target / "coa_uploads" / "report.pdf").read_bytes() == b"%PDF-1.4 real coa contents"


def test_restore_overwrites_an_existing_database_at_the_target(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_sqlite_db(source_dir / "canopy.db")
    backup_dir = tmp_path / "backups"
    result = run_backup(db_path=source_dir / "canopy.db", coa_dir=tmp_path / "no-coas", backup_dir=backup_dir)

    restore_target = tmp_path / "restored"
    restore_target.mkdir()
    stale_db = restore_target / "canopy.db"
    conn = sqlite3.connect(stale_db)
    conn.execute("CREATE TABLE rooms (id TEXT)")
    conn.execute("INSERT INTO rooms VALUES ('stale-room-that-should-be-gone')")
    conn.commit()
    conn.close()

    restore_backup(result.path, data_dir=restore_target)

    conn = sqlite3.connect(stale_db)
    rooms = [r[0] for r in conn.execute("SELECT id FROM rooms").fetchall()]
    conn.close()
    assert rooms == ["greenhouse-a", "greenhouse-b"]
    assert "stale-room-that-should-be-gone" not in rooms


def test_restore_rejects_an_archive_with_no_database_in_it(tmp_path):
    fake_archive = tmp_path / "not-a-real-backup.tar.gz"
    with tarfile.open(fake_archive, "w:gz") as tar:
        info = tarfile.TarInfo(name="some_other_file.txt")
        data = b"not a canopy backup"
        info.size = len(data)
        import io
        tar.addfile(info, io.BytesIO(data))

    restore_target = tmp_path / "restored"
    with pytest.raises(ValueError, match="does not contain a canopy.db"):
        restore_backup(fake_archive, data_dir=restore_target)

    assert not restore_target.exists()  # never touched — validation happens before any real files change


def test_restore_rejects_a_corrupt_database_without_touching_the_target(tmp_path):
    archive = tmp_path / "corrupt-backup.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        import io
        garbage = b"this is not a valid sqlite file, just garbage bytes"
        info = tarfile.TarInfo(name="canopy.db")
        info.size = len(garbage)
        tar.addfile(info, io.BytesIO(garbage))

    restore_target = tmp_path / "restored"
    restore_target.mkdir()
    (restore_target / "canopy.db").write_bytes(b"the real, still-good database")

    with pytest.raises(sqlite3.DatabaseError):
        restore_backup(archive, data_dir=restore_target)

    # the pre-existing (good) database must survive a failed restore untouched
    assert (restore_target / "canopy.db").read_bytes() == b"the real, still-good database"
