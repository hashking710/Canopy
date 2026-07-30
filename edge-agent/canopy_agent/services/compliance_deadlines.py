from datetime import datetime, timedelta, timezone

from canopy_agent.compliance_rules import get_rules
from canopy_agent.compliance_rules.base import StateComplianceRules


def add_business_days(start: datetime, business_days: float) -> datetime:
    current = start
    remaining = business_days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Monday=0 ... Friday=4
            remaining -= 1
    return current


def waste_reporting_deadline(occurred_at: datetime, state_code: str | None = None) -> datetime | None:
    """
    Only "hours_after_occurrence" and "business_days_after_occurrence" are actually a
    *report-by* deadline computable from when the waste occurred — the other
    deadline_kind shapes found by research aren't that kind of obligation at all:
    "pre_destruction_notice_days" and "destroy_by_days_after_logging" are keyed off a
    different timestamp (a notice sent, or when it was logged) than `occurred_at`, and
    "no_deadline_found"/"unknown" have no deadline to compute in the first place. This
    returns None for all of those rather than a fabricated number — a caller that needs
    a concrete date is a caller that shouldn't have assumed one exists.
    """
    rules: StateComplianceRules = get_rules(state_code)
    if rules.deadline_kind == "hours_after_occurrence" and rules.deadline_value is not None:
        return occurred_at + timedelta(hours=rules.deadline_value)
    if rules.deadline_kind == "business_days_after_occurrence" and rules.deadline_value is not None:
        return add_business_days(occurred_at, rules.deadline_value)
    return None


def is_waste_overdue(
    occurred_at: datetime,
    reported_at: datetime | None = None,
    now: datetime | None = None,
    state_code: str | None = None,
) -> bool | None:
    """None means "not modeled for the active state's deadline shape" — distinct from
    False ("modeled, and not overdue"). Callers must not treat None as "fine"."""
    if reported_at is not None:
        return False  # already filed with the state — the deadline no longer applies
    deadline = waste_reporting_deadline(occurred_at, state_code)
    if deadline is None:
        return None
    now = now or datetime.now(timezone.utc)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now > deadline
