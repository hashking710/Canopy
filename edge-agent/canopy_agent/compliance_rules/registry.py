import os

from canopy_agent.compliance_rules import (
    arizona,
    california,
    colorado,
    florida,
    illinois,
    maryland,
    massachusetts,
    michigan,
    missouri,
    nevada,
    new_jersey,
    new_york,
    ohio,
    oklahoma,
)
from canopy_agent.compliance_rules.base import StateComplianceRules

_STATES: dict[str, StateComplianceRules] = {
    r.state_code: r
    for r in [
        arizona.RULES,
        california.RULES,
        colorado.RULES,
        florida.RULES,
        illinois.RULES,
        maryland.RULES,
        massachusetts.RULES,
        michigan.RULES,
        missouri.RULES,
        nevada.RULES,
        new_jersey.RULES,
        new_york.RULES,
        ohio.RULES,
        oklahoma.RULES,
    ]
}

# One edge agent represents one facility, so its compliance state is a single fact per
# facility, not something that varies per request. Falls back to CANOPY_COMPLIANCE_STATE
# (a deployment-time env var, same as CANOPY_SITE_ID) or this default when no operator
# has explicitly set one via POST /api/compliance/state-rules — see
# services/facility_state.py, which checks a database-backed override first. Defaults to
# California, which remains among the most thoroughly primary-source-verified states in
# this dataset after a deeper research pass (Arizona is now comparably thorough on most
# fields) — every state still has at least one field that's secondary-sourced,
# unconfirmed, or an actively disputed conflict; see each module's `notes` before relying
# on a non-CA state.
DEFAULT_STATE_CODE = "CA"


def get_rules(state_code: str | None = None) -> StateComplianceRules:
    code = (state_code or os.environ.get("CANOPY_COMPLIANCE_STATE") or DEFAULT_STATE_CODE).upper()
    try:
        return _STATES[code]
    except KeyError:
        known = ", ".join(sorted(_STATES))
        raise ValueError(f"no compliance rules for state '{code}' — known states: {known}") from None


def list_states() -> list[StateComplianceRules]:
    return sorted(_STATES.values(), key=lambda r: r.state_code)
