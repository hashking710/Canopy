from fastapi import APIRouter, HTTPException

from canopy_master.store import store

router = APIRouter(prefix="/api/sites", tags=["sites"])


@router.get("")
def list_sites() -> list[dict]:
    return store.site_summaries()


@router.get("/{site_id}/rooms")
def get_site_rooms(site_id: str) -> list[dict]:
    if site_id not in store.sites:
        raise HTTPException(status_code=404, detail="site not found (no messages received from it yet)")
    return store.rooms_for_site(site_id)
