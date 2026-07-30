from datetime import datetime, timedelta, timezone

from canopy_agent.services.reconciliation import is_recount_stale


def test_no_cadence_never_stale():
    old = datetime.now(timezone.utc) - timedelta(days=365)
    assert is_recount_stale(old, cadence_days=None) is False


def test_within_cadence_not_stale():
    counted_at = datetime.now(timezone.utc) - timedelta(hours=1)
    assert is_recount_stale(counted_at, cadence_days=1) is False


def test_beyond_cadence_is_stale():
    counted_at = datetime.now(timezone.utc) - timedelta(days=2)
    assert is_recount_stale(counted_at, cadence_days=1) is True


def test_naive_datetime_from_sqlite_round_trip_still_works():
    # SQLite hands DateTime columns back naive — must not crash comparing tz-aware `now`
    # against a naive `counted_at`, and must not misjudge staleness from the round-trip.
    counted_at_naive = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None)
    assert is_recount_stale(counted_at_naive, cadence_days=1) is False

    stale_naive = (datetime.now(timezone.utc) - timedelta(days=5)).replace(tzinfo=None)
    assert is_recount_stale(stale_naive, cadence_days=1) is True
