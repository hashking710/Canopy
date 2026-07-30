from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from canopy_agent.deps import get_db
from canopy_agent.models import Room
from canopy_agent.schemas import RoomOut
from canopy_agent.stats import facility_payload

router = APIRouter(prefix="/api/facility", tags=["facility"])


class CreateFacilityRequest(BaseModel):
    title: str = ""
    subtitle: str = "plants on site, right now"
    badge: str = ""
    footnote: str = ""
    section: str = "the facility"


@router.get("", response_model=RoomOut)
def get_facility(db: Session = Depends(get_db)) -> RoomOut:
    facility = db.get(Room, "facility")
    if facility is None:
        raise HTTPException(status_code=404, detail="facility not seeded")
    return RoomOut(**facility_payload(db, facility))


@router.post("", response_model=RoomOut)
def create_facility(body: CreateFacilityRequest, db: Session = Depends(get_db)) -> RoomOut:
    """
    First-run setup — the facility row is a singleton with a fixed id ("facility",
    matching get_facility's lookup above), not user-supplied, since there's exactly
    one per device. Regular rooms are created via POST /api/rooms once this exists.
    """
    if db.get(Room, "facility") is not None:
        raise HTTPException(status_code=400, detail="a facility is already configured on this device")

    facility = Room(
        id="facility", room_type="facility", path="facility",
        title=body.title, subtitle=body.subtitle, badge=body.badge, footnote=body.footnote, section=body.section,
        metric_config={},
    )
    db.add(facility)
    db.commit()
    return RoomOut(**facility_payload(db, facility))
