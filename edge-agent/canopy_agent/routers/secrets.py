import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from canopy_agent.adapters.registry import available_adapter_types
from canopy_agent.compliance_sync.registry import available_sync_types
from canopy_agent.deps import get_db
from canopy_agent.menu_sync.registry import available_sync_types as available_menu_sync_types
from canopy_agent.models import FacilitySecret, utcnow
from canopy_agent.services.operators import get_active_operator, pin_check_failed, require_role

router = APIRouter(prefix="/api/secrets", tags=["secrets"])


class SetSecretRequest(BaseModel):
    value: str
    operator_id: str
    pin: str | None = None


class ClearSecretRequest(BaseModel):
    operator_id: str
    pin: str | None = None


def _require_admin_operator(db: Session, operator_id: str, pin: str | None) -> None:
    """Credentials are the most sensitive "change settings" category this facility
    has — gated at role >= admin, same PIN-if-configured pattern the compliance
    router already uses for destruction actions, not a new mechanism."""
    operator = get_active_operator(db, operator_id)
    if operator is None:
        raise HTTPException(status_code=404, detail=f"operator '{operator_id}' not found or inactive")
    if pin_check_failed(operator, pin):
        raise HTTPException(status_code=401, detail=f"PIN required or incorrect for operator '{operator.name}'")
    require_role(operator, "admin")


def _known_secret_keys() -> dict[str, str]:
    """key -> description, aggregated from every *installed* sensor adapter's,
    compliance-sync plugin's, and menu-sync plugin's required_env_vars — the same
    source the room-creation UI's EnvVarNotice already reads from, so this list only
    ever contains credentials something actually installed can use. Not a
    general-purpose env var editor: routers below reject any key not found here.
    This is also how Weedmaps/mock menu-sync credentials show up in the dashboard's
    credentials settings without a dedicated integrations UI of their own — see
    menu_sync/base.py's own docstring."""
    known: dict[str, str] = {}
    for adapter_cls in available_adapter_types().values():
        known.update(adapter_cls.required_env_vars)
    for sync_cls in available_sync_types().values():
        known.update(sync_cls.required_env_vars)
    for menu_sync_cls in available_menu_sync_types().values():
        known.update(menu_sync_cls.required_env_vars)
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
    _require_admin_operator(db, body.operator_id, body.pin)

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
def clear_secret(key: str, body: ClearSecretRequest, db: Session = Depends(get_db)) -> dict:
    _require_admin_operator(db, body.operator_id, body.pin)

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
