import pytest

from canopy_agent.compliance_rules import get_rules
from canopy_agent.compliance_rules.registry import list_states

EXPECTED_STATES = {"AZ", "CA", "CO", "IL", "MD", "MA", "MI", "MO", "NV", "OH", "OK"}


def test_defaults_to_california():
    rules = get_rules()
    assert rules.state_code == "CA"
    assert rules.deadline_confidence == "primary_source"


def test_explicit_state_code_overrides_default():
    rules = get_rules("CO")
    assert rules.state_code == "CO"


def test_state_code_is_case_insensitive():
    assert get_rules("ca").state_code == "CA"


def test_env_var_selects_state(monkeypatch):
    monkeypatch.setenv("CANOPY_COMPLIANCE_STATE", "OK")
    assert get_rules().state_code == "OK"


def test_explicit_arg_wins_over_env_var(monkeypatch):
    monkeypatch.setenv("CANOPY_COMPLIANCE_STATE", "OK")
    assert get_rules("CA").state_code == "CA"


def test_unknown_state_raises():
    with pytest.raises(ValueError, match="no compliance rules for state"):
        get_rules("ZZ")


def test_list_states_includes_all_researched_states_sorted():
    codes = {r.state_code for r in list_states()}
    assert codes == EXPECTED_STATES
    sorted_codes = [r.state_code for r in list_states()]
    assert sorted_codes == sorted(sorted_codes)


def test_california_has_the_strongest_sourced_waste_deadline():
    # Documents the current honest state of research — CA's 24-hour deadline is the
    # only one confirmed against primary regulation text as an actual "report within
    # N hours" figure; every other state either has a different deadline shape, an
    # explicitly confirmed absence of a deadline, or unverified/unknown sourcing.
    ca = next(r for r in list_states() if r.state_code == "CA")
    assert ca.deadline_kind == "hours_after_occurrence"
    assert ca.deadline_confidence == "primary_source"


def test_no_state_platform_is_assumed_metrc_without_checking():
    # Arizona has no state track-and-trace platform at all — a real, researched fact,
    # not a gap. If this ever flips to "metrc" it means someone silently regressed
    # the platform field back to an assumption instead of a researched value.
    az = next(r for r in list_states() if r.state_code == "AZ")
    assert az.platform == "none"


def test_some_states_tag_by_size_not_phase():
    mi = next(r for r in list_states() if r.state_code == "MI")
    assert mi.tagging_trigger_kind == "size"


def test_some_states_have_no_deadline_found_rather_than_unresearched():
    # "no_deadline_found" (confirmed absence, checked against primary text) is a
    # different claim than "unknown" (not yet researched) — distinct literals so one
    # is never mistaken for the other.
    kinds = {r.state_code: r.deadline_kind for r in list_states()}
    assert kinds["MI"] == "no_deadline_found"
    assert kinds["OK"] == "no_deadline_found"
    # Arizona was the only state still "unknown" (deadline shape not yet researched at
    # all) as of the prior research pass; a later, deeper pass resolved it too — R9-17-316
    # and R9-18-314, read directly, require disposal to be documented but set no deadline.
    # Every one of the 11 states now has a confirmed deadline_kind rather than an
    # unresearched one — "unknown" remains a real literal for any future state added
    # without research yet, it's just not exercised by the current 11.
    assert kinds["AZ"] == "no_deadline_found"
    assert "unknown" not in kinds.values()
