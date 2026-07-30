import os

from sqlalchemy.orm import Session

from canopy_agent.compliance_models import FacilityComplianceState, utcnow
from canopy_agent.compliance_rules import get_rules
from canopy_agent.compliance_rules.base import StateComplianceRules
from canopy_agent.compliance_rules.registry import DEFAULT_STATE_CODE

# Always exactly one row (see FacilityComplianceState's docstring), same pattern as
# RelayCursor's fixed row names.
FACILITY_STATE_ROW_ID = "facility"


def get_active_state_code(db: Session) -> str:
    """
    An operator explicitly setting this via POST /state-rules (stored here, in the
    database) is a real fact about the facility, and takes precedence over
    CANOPY_COMPLIANCE_STATE — which remains the fallback for contexts with no
    database at all (a fresh install that's never set this, or a pure caller like the
    community bot that only ever calls compliance_rules.get_rules() directly).
    """
    row = db.get(FacilityComplianceState, FACILITY_STATE_ROW_ID)
    if row is not None:
        return row.state_code
    return os.environ.get("CANOPY_COMPLIANCE_STATE") or DEFAULT_STATE_CODE


def get_active_rules(db: Session) -> StateComplianceRules:
    return get_rules(get_active_state_code(db))


def set_active_state_code(db: Session, state_code: str, actor: str) -> FacilityComplianceState:
    """Raises ValueError (via get_rules) if state_code isn't a known state — never
    silently accepts an invalid jurisdiction."""
    code = state_code.upper()
    get_rules(code)  # validates; raises ValueError with the known-states list if not

    row = db.get(FacilityComplianceState, FACILITY_STATE_ROW_ID)
    if row is None:
        row = FacilityComplianceState(id=FACILITY_STATE_ROW_ID, state_code=code, updated_by=actor)
        db.add(row)
    else:
        row.state_code = code
        row.updated_by = actor
    row.updated_at = utcnow()
    db.flush()
    return row
