import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from canopy_agent.adapters.registry import available_adapter_types
from canopy_agent.compliance_sync.registry import available_sync_types
from canopy_agent.deps import get_db
from canopy_agent.models import FacilitySecret, utcnow

router = APIRouter(prefix="/api/secrets", tags=["secrets"])


class SetSecretRequest(BaseModel):
    value: str


def _known_secret_keys() -> dict[str, str]:
    """key -> description, aggregated from every *installed* sensor adapter's and
    compliance-sync plugin's required_env_vars — the same source the room-creation
    UI's EnvVarNotice already reads from, so this list only ever contains
    credentials something actually installed can use. Not a general-purpose env
    var editor: routers below reject any key not found here."""
    known: dict[str, str] = {}
    for adapter_cls in available_adapter_types().values():
        known.update(adapter_cls.required_env_vars)
    for sync_cls in available_sync_types().values():
        known.update(sync_cls.required_env_vars)
    return known


@router.get("")
def list_secrets(db: Session = Depends(get_db)) -> list[dict]:
    """Never returns a value — only whether each known credential is currently set
    (from the database or, as a fallback, an env var set outside the app, e.g. via
    docker-compose.yml) and which plugin(s) need it, so the dashboard can show a
    clear "needs setup" / "configured" state without ever exposing the secret
    itself back over the API."""
    known = _known_secret_keys()
    stored_keys = set(db.execute(select(FacilitySecret.key)).scalars().all())
    return [
        {
            "key": key,
            "description": description,
            "is_set": key in stored_keys or bool(os.environ.get(key)),
            "set_via_dashboard": key in stored_keys,
        }
        for key, description in sorted(known.items())
    ]


@router.put("/{key}")
def set_secret(key: str, body: SetSecretRequest, db: Session = Depends(get_db)) -> dict:
    known = _known_secret_keys()
    if key not in known:
        raise HTTPException(
            status_code=400,
            detail=f"unknown secret key '{key}' — not required by any installed adapter or sync plugin",
        )
    if not body.value.strip():
        raise HTTPException(status_code=400, detail="value must not be empty — use DELETE to clear a secret")

    row = db.get(FacilitySecret, key)
    if row is None:
        row = FacilitySecret(key=key, value=body.value)
        db.add(row)
    else:
        row.value = body.value
    row.updated_at = utcnow()
    db.commit()

    # Takes effect immediately, not just after a restart — every cloud adapter reads
    # its credential fresh from os.environ on each read()/sync call rather than
    # caching it at __init__ (see e.g. plugins/canopy-adapter-govee's read()), so
    # the very next poll cycle picks this up.
    os.environ[key] = body.value
    return {"key": key, "is_set": True}


@router.delete("/{key}")
def clear_secret(key: str, db: Session = Depends(get_db)) -> dict:
    known = _known_secret_keys()
    if key not in known:
        raise HTTPException(
            status_code=400,
            detail=f"unknown secret key '{key}' — not required by any installed adapter or sync plugin",
        )
    row = db.get(FacilitySecret, key)
    if row is not None:
        db.delete(row)
        db.commit()
    os.environ.pop(key, None)
    return {"key": key, "is_set": bool(os.environ.get(key))}
