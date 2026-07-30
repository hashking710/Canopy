"""
Restores a backup created by services/backup.py.

Deliberately a standalone script, not an API endpoint on the running app: safely
replacing a SQLite file (and the COA upload files) out from under a process that has
them open isn't something the app can do to itself mid-request. The intended
procedure is: stop the container, run this against the mounted data volume, start it
again — e.g.

    docker compose stop edge-agent
    docker run --rm -v canopy_edge-agent-data:/data -v $(pwd):/backup \\
        canopy-edge-agent python -m canopy_agent.restore /backup/canopy-backup-*.tar.gz
    docker compose start edge-agent

or, run directly on the host if CANOPY_DATA_DIR points at a real filesystem path
rather than a Docker volume.
"""

import argparse
import shutil
import sqlite3
import sys
import tarfile
import tempfile
from pathlib import Path

from canopy_agent.db import DATA_DIR


def _verify_sqlite_file(path: Path) -> None:
    """Opens the extracted DB and runs an integrity check before touching anything
    real — a corrupt or truncated backup archive must fail loudly right here, not
    silently replace a working database with a broken one."""
    conn = sqlite3.connect(path)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise ValueError(f"backup's database failed integrity check: {result}")
    finally:
        conn.close()


def restore_backup(archive_path: Path, data_dir: Path = DATA_DIR) -> None:
    """Extracts to a temp location and validates first, then swaps the real files in
    last — if anything above is wrong (missing canopy.db, a corrupt database), the
    real data directory is never touched at all."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with tarfile.open(archive_path) as tar:
            tar.extractall(tmp_path, filter="data")

        extracted_db = tmp_path / "canopy.db"
        if not extracted_db.exists():
            raise ValueError(f"'{archive_path}' does not contain a canopy.db — not a valid Canopy backup archive")
        _verify_sqlite_file(extracted_db)

        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = data_dir / "canopy.db"
        if db_path.exists():
            db_path.unlink()
        shutil.move(str(extracted_db), str(db_path))

        extracted_coa = tmp_path / "coa_uploads"
        if extracted_coa.exists():
            target_coa = data_dir / "coa_uploads"
            if target_coa.exists():
                shutil.rmtree(target_coa)
            shutil.move(str(extracted_coa), str(target_coa))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Restore a Canopy backup created by services/backup.py. Run with the app STOPPED."
    )
    parser.add_argument("archive", type=Path, help="Path to a canopy-backup-*.tar.gz file")
    parser.add_argument(
        "--data-dir", type=Path, default=DATA_DIR,
        help="Target data directory (defaults to CANOPY_DATA_DIR, same as the app itself uses)",
    )
    args = parser.parse_args()

    if not args.archive.exists():
        print(f"error: '{args.archive}' does not exist", file=sys.stderr)
        sys.exit(1)

    restore_backup(args.archive, args.data_dir)
    print(f"restored '{args.archive}' into '{args.data_dir}'")


if __name__ == "__main__":
    main()
