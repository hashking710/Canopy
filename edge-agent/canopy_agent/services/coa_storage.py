"""
Storage for uploaded COA (Certificate of Analysis) documents — the lab's own report,
attached to a LabTest record as-is for inspections. Deliberately does NOT parse the
file: lab PDF layouts vary too much per-lab to extract fields reliably, and getting a
THC%/pass-fail figure silently wrong from a misread PDF would be worse than the
manual entry it replaced. See LabTest.coa_filename/coa_stored_path in
compliance_models.py.
"""

import uuid
from pathlib import Path

from fastapi import UploadFile

from canopy_agent.db import DATA_DIR

COA_DIR = DATA_DIR / "coa_uploads"
COA_DIR.mkdir(parents=True, exist_ok=True)

# Just enough to cover what labs actually send back: a PDF report, or a phone photo/
# scan of a printed one.
_ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}
_MAX_BYTES = 20 * 1024 * 1024  # 20MB — comfortably above a real multi-page lab PDF


class CoaUploadError(ValueError):
    pass


async def save_coa(upload: UploadFile) -> tuple[str, str]:
    """Returns (stored_path, filename) for LabTest.coa_stored_path/coa_filename.
    stored_path is a generated uuid-based name, never derived from the original
    filename — the original is kept only as display text, not trusted as a path
    component."""
    ext = _ALLOWED_CONTENT_TYPES.get(upload.content_type or "")
    if ext is None:
        raise CoaUploadError(f"unsupported file type '{upload.content_type}' — upload a PDF, PNG, or JPEG")

    data = await upload.read()
    if len(data) == 0:
        raise CoaUploadError("uploaded file is empty")
    if len(data) > _MAX_BYTES:
        raise CoaUploadError(f"file too large ({len(data) // 1024 // 1024}MB) — max is {_MAX_BYTES // 1024 // 1024}MB")

    stored_name = f"{uuid.uuid4().hex}{ext}"
    (COA_DIR / stored_name).write_bytes(data)
    return stored_name, (upload.filename or stored_name)


def coa_path(stored_path: str) -> Path:
    """Resolves a stored_path back to a real file, refusing anything that isn't a
    plain filename directly inside COA_DIR (defense in depth against a stored_path
    that somehow contains path separators)."""
    candidate = COA_DIR / Path(stored_path).name
    if candidate.parent != COA_DIR:
        raise CoaUploadError("invalid stored path")
    return candidate
