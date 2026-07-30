import os

from fastapi import Header, HTTPException

# Simple shared-secret auth, distinct from each edge agent's own CANOPY_API_TOKEN —
# this one gates the aggregated cross-site view, i.e. "master admin" access. Unset
# means auth is off, so local dev keeps working with zero configuration.
MASTER_TOKEN = os.environ.get("CANOPY_MASTER_TOKEN")


def is_valid_token(token: str | None) -> bool:
    return MASTER_TOKEN is None or token == MASTER_TOKEN


def require_token(authorization: str | None = Header(default=None)) -> None:
    """HTTP gate — attach via `app.include_router(..., dependencies=[Depends(require_token)])`."""
    presented = authorization.removeprefix("Bearer ") if authorization else None
    if not is_valid_token(presented):
        raise HTTPException(status_code=401, detail="missing or invalid master token")
