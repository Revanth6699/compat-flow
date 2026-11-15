from datetime import datetime, timedelta, timezone

import pytest

from app.services.subscription_period import subscription_period_end


@pytest.mark.parametrize(
    "paid_at",
    [
        datetime(2026, 11, 15, 11, 36, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 31, 11, 36, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 31, 11, 36, 0, tzinfo=timezone.utc),
        datetime(2026, 2, 28, 11, 36, 0, tzinfo=timezone.utc),
    ],
)
def test_monthly_period_is_exactly_30_days(paid_at):
    assert subscription_period_end(paid_at, "month") == paid_at + timedelta(days=30)


def test_january_31_expires_march_2_in_non_leap_year():
    paid_at = datetime(2026, 1, 31, 11, 36, 0, tzinfo=timezone.utc)
    assert subscription_period_end(paid_at, "month") == datetime(
        2026, 3, 2, 11, 36, 0, tzinfo=timezone.utc
    )


def test_february_28_expires_march_30():
    paid_at = datetime(2026, 2, 28, 11, 36, 0, tzinfo=timezone.utc)
    assert subscription_period_end(paid_at, "month") == datetime(
        2026, 3, 30, 11, 36, 0, tzinfo=timezone.utc
    )


def test_yearly_period_preserves_exact_payment_time():
    paid_at = datetime(2026, 11, 15, 11, 36, 0, tzinfo=timezone.utc)
    assert subscription_period_end(paid_at, "year") == datetime(
        2027, 11, 15, 11, 36, 0, tzinfo=timezone.utc
    )


def test_period_rejects_naive_timestamp():
    with pytest.raises(ValueError, match="timezone-aware"):
        subscription_period_end(datetime(2026, 11, 15, 11, 36), "month")
