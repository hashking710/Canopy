import os

from fastapi import Header, HTTPException

# Simple shared-secret auth, not user accounts — fits a single site/device, not a
# multi-tenant system. Unset (the default) means auth is off, so local dev and a
# single-operator setup keep working with zero configuration.
API_TOKEN = os.environ.get("CANOPY_API_TOKEN")


def is_valid_token(token: str | None) -> bool:
    return API_TOKEN is None or token == API_TOKEN


def require_token(authorization: str | None = Header(default=None)) -> None:
    """HTTP gate — attach via `app.include_router(..., dependencies=[Depends(require_token)])`."""
    presented = authorization.removeprefix("Bearer ") if authorization else None
    if not is_valid_token(presented):
        raise HTTPException(status_code=401, detail="missing or invalid API token")
