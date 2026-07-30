from sqlalchemy.orm import Session

from canopy_agent.compliance_models import FacilitySecuritySettings, utcnow

# Always exactly one row (see FacilityComplianceState's docstring — same pattern).
FACILITY_SECURITY_ROW_ID = "facility"


def get_require_operator_pins(db: Session) -> bool:
    row = db.get(FacilitySecuritySettings, FACILITY_SECURITY_ROW_ID)
    return row.require_operator_pins if row is not None else False


def set_require_operator_pins(db: Session, value: bool, actor: str) -> FacilitySecuritySettings:
    row = db.get(FacilitySecuritySettings, FACILITY_SECURITY_ROW_ID)
    if row is None:
        row = FacilitySecuritySettings(id=FACILITY_SECURITY_ROW_ID, require_operator_pins=value, updated_by=actor)
        db.add(row)
    else:
        row.require_operator_pins = value
        row.updated_by = actor
    row.updated_at = utcnow()
    db.flush()
    return row
