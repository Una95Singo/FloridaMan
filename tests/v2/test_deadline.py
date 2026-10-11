"""Review deadline rule: earliest of the next 09:00/21:00 UTC window, first
request plus twelve hours, or the decision horizon (WORKFLOW_CONTRACT section 4,
FR-013)."""

from datetime import datetime, timezone, timedelta

import pytest

from server.domain import review_deadline

UTC = timezone.utc


def at(h, m=0, day=10):
    return datetime(2026, 10, day, h, m, tzinfo=UTC)


def test_morning_request_meets_the_morning_window():
    assert review_deadline(at(6, 30)) == at(9)


def test_afternoon_request_meets_the_evening_window():
    assert review_deadline(at(14, 7)) == at(21)


def test_late_evening_request_meets_the_next_morning_window():
    # 22:00 plus twelve hours is 10:00 the next day; 09:00 comes first.
    assert review_deadline(at(22)) == at(9, day=11)


def test_request_exactly_on_a_window_uses_the_next_window():
    assert review_deadline(at(9)) == at(21)
    assert review_deadline(at(21)) == at(9, day=11)


def test_deadline_never_exceeds_twelve_hours():
    for hour in range(24):
        for minute in (0, 1, 30, 59):
            start = at(hour, minute)
            assert start < review_deadline(start) <= start + timedelta(hours=12)


def test_decision_horizon_wins_when_earliest():
    assert review_deadline(at(6), at(8)) == at(8)


def test_decision_horizon_does_not_extend_the_deadline():
    assert review_deadline(at(6), at(23)) == at(9)


def test_accepts_iso_strings_and_normalizes_to_utc():
    local = "2026-10-10T02:30:00-04:00"  # 06:30 UTC
    assert review_deadline(local) == at(9)
    assert review_deadline(local, "2026-10-10T04:00:00-04:00") == at(8)


def test_naive_datetimes_are_rejected():
    with pytest.raises(ValueError):
        review_deadline(datetime(2026, 10, 10, 6))
    with pytest.raises(ValueError):
        review_deadline(at(6), datetime(2026, 10, 10, 8))
