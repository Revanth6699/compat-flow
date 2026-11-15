from datetime import datetime, timezone

import pytest

from app.services.subscription_period import subscription_period_end


def test_monthly_period_preserves_exact_payment_time():
    paid_at = datetime(2026, 11, 15, 11, 36, 0, tzinfo=timezone.utc)
    assert subscription_period_end(paid_at, "month") == datetime(
        2026, 12, 15, 11, 36, 0, tzinfo=timezone.utc
    )


def test_monthly_period_clamps_to_last_day_of_shorter_month():
    paid_at = datetime(2026, 1, 31, 11, 36, 0, tzinfo=timezone.utc)
    assert subscription_period_end(paid_at, "month") == datetime(
        2026, 2, 28, 11, 36, 0, tzinfo=timezone.utc
    )


def test_monthly_period_handles_leap_year():
    paid_at = datetime(2024, 1, 31, 11, 36, 0, tzinfo=timezone.utc)
    assert subscription_period_end(paid_at, "month") == datetime(
        2024, 2, 29, 11, 36, 0, tzinfo=timezone.utc
    )


def test_yearly_period_preserves_exact_payment_time():
    paid_at = datetime(2026, 11, 15, 11, 36, 0, tzinfo=timezone.utc)
    assert subscription_period_end(paid_at, "year") == datetime(
        2027, 11, 15, 11, 36, 0, tzinfo=timezone.utc
    )


def test_period_rejects_naive_timestamp():
    with pytest.raises(ValueError, match="timezone-aware"):
        subscription_period_end(datetime(2026, 11, 15, 11, 36), "month")
