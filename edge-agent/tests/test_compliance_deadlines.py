from datetime import datetime, timezone

import canopy_agent.services.compliance_deadlines as deadlines
from canopy_agent.compliance_rules.base import HomeGrowRules, RetailRules, StateComplianceRules
from canopy_agent.services.compliance_deadlines import add_business_days, is_waste_overdue, waste_reporting_deadline

_NO_HOME_GROW = HomeGrowRules(
    recreational_allowed=False, recreational_limit=None,
    medical_allowed=False, medical_limit=None,
    extended_medical_available=False, extended_medical_limit=None, extended_medical_note="",
    caregiver_limit=None, caregiver_max_patients=None,
    geographic_gate=None, confidence="could_not_verify", notes="",
)

_NO_RETAIL = RetailRules(
    recreational_allowed=False, recreational_purchase_limits=(), recreational_min_age=None,
    medical_allowed=False, medical_purchase_limits=(), medical_min_age=None,
    id_verification_required=None, id_verification_note="",
    pos_realtime_sync_required=None, pos_realtime_sync_note="",
    confidence="could_not_verify", notes="",
)


def _fake_rules(deadline_kind: str, deadline_value: float | None) -> StateComplianceRules:
    return StateComplianceRules(
        state_code="ZZ", state_name="Test State",
        platform="metrc", platform_confidence="could_not_verify",
        tagging_trigger_kind="unknown", tagging_trigger_value="", tagging_trigger_confidence="could_not_verify",
        deadline_kind=deadline_kind, deadline_value=deadline_value, deadline_confidence="could_not_verify",
        reconciliation_cadence_days=None, reconciliation_confidence="could_not_verify",
        testing_required_for_solvent_extracts=None, testing_confidence="could_not_verify", testing_note="",
        home_grow=_NO_HOME_GROW, retail=_NO_RETAIL, notes="test fixture",
    )


def test_add_business_days_skips_weekend():
    # Thursday 2026-07-23 + 3 business days -> Tue 2026-07-28 (skips Sat/Sun)
    start = datetime(2026, 7, 23, tzinfo=timezone.utc)
    result = add_business_days(start, 3)
    assert result == datetime(2026, 7, 28, tzinfo=timezone.utc)


def test_waste_reporting_deadline_defaults_to_california_24_hours():
    occurred = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
    assert waste_reporting_deadline(occurred) == datetime(2026, 7, 21, 9, 0, tzinfo=timezone.utc)


def test_waste_reporting_deadline_explicit_state_code():
    occurred = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
    assert waste_reporting_deadline(occurred, state_code="CA") == datetime(2026, 7, 21, 9, 0, tzinfo=timezone.utc)


def test_waste_reporting_deadline_dispatches_to_business_days(monkeypatch):
    fake_rules = _fake_rules("business_days_after_occurrence", 3)
    monkeypatch.setattr(deadlines, "get_rules", lambda state_code=None: fake_rules)

    occurred = datetime(2026, 7, 20, tzinfo=timezone.utc)  # Monday
    assert waste_reporting_deadline(occurred) == datetime(2026, 7, 23, tzinfo=timezone.utc)


def test_waste_reporting_deadline_is_none_for_no_deadline_found(monkeypatch):
    fake_rules = _fake_rules("no_deadline_found", None)
    monkeypatch.setattr(deadlines, "get_rules", lambda state_code=None: fake_rules)
    assert waste_reporting_deadline(datetime.now(timezone.utc)) is None


def test_waste_reporting_deadline_is_none_for_pre_destruction_notice_shape(monkeypatch):
    # Not a "report by X after occurrence" deadline at all — this project doesn't model
    # notify-before-destruction obligations yet, and must not fabricate a fake date.
    fake_rules = _fake_rules("pre_destruction_notice_days", 7)
    monkeypatch.setattr(deadlines, "get_rules", lambda state_code=None: fake_rules)
    assert waste_reporting_deadline(datetime.now(timezone.utc)) is None


def test_is_waste_overdue_returns_none_when_no_deadline_is_modeled(monkeypatch):
    fake_rules = _fake_rules("unknown", None)
    monkeypatch.setattr(deadlines, "get_rules", lambda state_code=None: fake_rules)
    assert is_waste_overdue(datetime.now(timezone.utc)) is None


def test_is_waste_overdue_false_before_deadline():
    occurred = datetime.now(timezone.utc)
    assert is_waste_overdue(occurred) is False


def test_is_waste_overdue_true_after_deadline():
    occurred = datetime(2020, 1, 1, tzinfo=timezone.utc)
    assert is_waste_overdue(occurred) is True


def test_is_waste_overdue_false_once_reported_even_if_late():
    occurred = datetime(2020, 1, 1, tzinfo=timezone.utc)
    reported = datetime(2020, 1, 10, tzinfo=timezone.utc)
    assert is_waste_overdue(occurred, reported_at=reported) is False
