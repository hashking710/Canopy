from fastapi import APIRouter

from canopy_agent.licensing.registry import get_license_gate

router = APIRouter(prefix="/api/license", tags=["license"])


@router.get("/status")
def get_license_status() -> dict:
    """Surfaces which tier/gate is active and its health — see LicenseGate.status().
    Deliberately never hidden behind a separate admin-only concept: an operator should
    always be able to see what's unlocked and why without digging through logs."""
    return get_license_gate().status()
