"""
Local, rotating snapshots of the SQLite DB + uploaded COA files — the only durable
system-of-record this device has (see compliance_models.py's docstring on why plants/
harvests/etc. live in SQLite rather than anywhere else). Deliberately does NOT reach
for cloud storage: this project runs on hardware (a Pi's SD card) the operator fully
controls, with no other paid/external dependency anywhere in edge-agent, so the
default here is a same-philosophy local snapshot — CANOPY_BACKUP_DIR just needs to
point at a mounted network share or external drive to become real off-device backup,
no new integration required to get there.
"""

import asyncio
import logging
import os
import sqlite3
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from canopy_agent.db import DATA_DIR, DB_PATH
from canopy_agent.services.coa_storage import COA_DIR
from canopy_agent.services.error_reporting import report_system_error
from canopy_agent.services.health import record_failure, record_success

logger = logging.getLogger("canopy_agent.backup")

BACKUP_DIR = Path(os.environ.get("CANOPY_BACKUP_DIR", DATA_DIR / "backups"))
BACKUP_INTERVAL_SECONDS = int(os.environ.get("CANOPY_BACKUP_INTERVAL_SECONDS", 86400))
BACKUP_RETENTION_COUNT = int(os.environ.get("CANOPY_BACKUP_RETENTION_COUNT", 14))
_FILENAME_PREFIX = "canopy-backup-"
_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"


@dataclass
class BackupResult:
    path: Path
    size_bytes: int
    created_at: datetime


def _snapshot_sqlite(db_path: Path, dest_path: Path) -> None:
    """Uses SQLite's own online backup API rather than copying the file directly —
    a plain file copy can catch the DB mid-write and capture a torn, corrupt page;
    the backup API produces a consistent snapshot even while the app keeps writing."""
    source = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        dest = sqlite3.connect(dest_path)
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()


def run_backup(db_path: Path = DB_PATH, coa_dir: Path = COA_DIR, backup_dir: Path = BACKUP_DIR) -> BackupResult:
    """Pure enough to unit test directly: pass explicit paths in, get a BackupResult
    back, nothing here depends on module import order or a running app."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    archive_path = backup_dir / f"{_FILENAME_PREFIX}{now.strftime(_TIMESTAMP_FORMAT)}.tar.gz"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_db_path = Path(tmp) / "canopy.db"
        if db_path.exists():
            _snapshot_sqlite(db_path, tmp_db_path)

        with tarfile.open(archive_path, "w:gz") as tar:
            if tmp_db_path.exists():
                tar.add(tmp_db_path, arcname="canopy.db")
            if coa_dir.exists() and any(coa_dir.iterdir()):
                tar.add(coa_dir, arcname="coa_uploads")

    _prune_old_backups(backup_dir)
    size_bytes = archive_path.stat().st_size
    logger.info("backup written: %s (%d bytes)", archive_path, size_bytes)
    return BackupResult(path=archive_path, size_bytes=size_bytes, created_at=now)


def _prune_old_backups(backup_dir: Path) -> None:
    backups = sorted(backup_dir.glob(f"{_FILENAME_PREFIX}*.tar.gz"))
    excess = len(backups) - BACKUP_RETENTION_COUNT
    for stale in backups[:max(excess, 0)]:
        stale.unlink()


def list_backups(backup_dir: Path = BACKUP_DIR) -> list[BackupResult]:
    if not backup_dir.exists():
        return []
    results = []
    for path in sorted(backup_dir.glob(f"{_FILENAME_PREFIX}*.tar.gz")):
        stat = path.stat()
        results.append(BackupResult(path=path, size_bytes=stat.st_size, created_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)))
    return results


async def backup_forever() -> None:
    while True:
        try:
            # run_backup does real, potentially slow disk I/O (copying the whole DB
            # via SQLite's backup API) — calling it directly here would block the
            # entire event loop for that whole duration, freezing every other request
            # this server is handling (dashboard loads, sensor polling, compliance
            # actions) until the backup finishes. to_thread keeps it off the loop.
            await asyncio.to_thread(run_backup)
            record_success("backup")
        except Exception as exc:
            logger.exception("scheduled backup failed")
            record_failure("backup")
            # Arguably the most important one to report of all three — a failed
            # backup has zero UI surfacing anywhere, and the whole point of this
            # system is being the durable fallback if the device itself fails; a
            # silent failure here could go unnoticed for weeks.
            await report_system_error("backup", "scheduled backup failed", exc)
        await asyncio.sleep(BACKUP_INTERVAL_SECONDS)
