import sqlite3
import tarfile
import time
from datetime import datetime, timezone

from canopy_agent.services.backup import BackupResult, list_backups, run_backup


def _make_sqlite_db(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE rooms (id TEXT)")
    conn.execute("INSERT INTO rooms VALUES ('greenhouse-a')")
    conn.commit()
    conn.close()


def test_backup_archives_the_db_and_coa_uploads(tmp_path):
    db_path = tmp_path / "canopy.db"
    _make_sqlite_db(db_path)
    coa_dir = tmp_path / "coa_uploads"
    coa_dir.mkdir()
    (coa_dir / "report.pdf").write_bytes(b"%PDF-1.4 fake")
    backup_dir = tmp_path / "backups"

    result = run_backup(db_path=db_path, coa_dir=coa_dir, backup_dir=backup_dir)

    assert result.path.exists()
    assert result.size_bytes > 0
    with tarfile.open(result.path) as tar:
        names = tar.getnames()
        assert "canopy.db" in names
        assert any(n.startswith("coa_uploads") and n.endswith("report.pdf") for n in names)

    # the archived DB must be a real, queryable snapshot, not a truncated/torn copy
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    with tarfile.open(result.path) as tar:
        tar.extractall(extracted, filter="data")
    conn = sqlite3.connect(extracted / "canopy.db")
    rows = conn.execute("SELECT id FROM rooms").fetchall()
    conn.close()
    assert rows == [("greenhouse-a",)]


def test_backup_does_not_error_on_a_fresh_install_with_no_db_or_coas_yet(tmp_path):
    result = run_backup(db_path=tmp_path / "does-not-exist.db", coa_dir=tmp_path / "no-coas", backup_dir=tmp_path / "backups")
    assert result.path.exists()  # still produces an (empty) archive, doesn't crash


def test_old_backups_are_pruned_beyond_the_retention_count(tmp_path, monkeypatch):
    monkeypatch.setattr("canopy_agent.services.backup.BACKUP_RETENTION_COUNT", 3)
    db_path = tmp_path / "canopy.db"
    _make_sqlite_db(db_path)
    backup_dir = tmp_path / "backups"

    for _ in range(5):
        run_backup(db_path=db_path, coa_dir=tmp_path / "no-coas", backup_dir=backup_dir)
        time.sleep(1.1)  # filenames are second-resolution timestamps — must not collide

    remaining = list_backups(backup_dir)
    assert len(remaining) == 3
    # the survivors must be the newest three, not an arbitrary three
    all_names = sorted(p.name for p in backup_dir.glob("canopy-backup-*.tar.gz"))
    assert [b.path.name for b in remaining] == all_names[-3:]


def test_list_backups_is_empty_when_the_directory_has_never_been_created(tmp_path):
    assert list_backups(tmp_path / "never-backed-up") == []


def test_backup_status_and_run_endpoints(client, monkeypatch, tmp_path):
    fake_result = BackupResult(path=tmp_path / "canopy-backup-fake.tar.gz", size_bytes=1234, created_at=datetime.now(timezone.utc))
    (tmp_path / "canopy-backup-fake.tar.gz").write_bytes(b"x")

    monkeypatch.setattr("canopy_agent.routers.backup.list_backups", lambda: [])
    monkeypatch.setattr("canopy_agent.routers.backup.run_backup", lambda: fake_result)

    status = client.get("/api/backup/status").json()
    assert status == {"count": 0, "latest": None, "backups": []}

    triggered = client.post("/api/backup/run").json()
    assert triggered["filename"] == "canopy-backup-fake.tar.gz"
    assert triggered["size_bytes"] == 1234
