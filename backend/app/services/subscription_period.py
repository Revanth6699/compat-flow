"""Calendar-based subscription periods anchored to verified payment timestamps."""

import calendar
from datetime import datetime


def subscription_period_end(paid_at: datetime, billing_interval: str) -> datetime:
    """Return the exact calendar-month/year anniversary of an aware payment timestamp.

    The wall-clock time and timezone are preserved. If the target month has fewer
    days than the payment date (for example, 31 January), clamp to its final day.
    """
    if paid_at.tzinfo is None or paid_at.utcoffset() is None:
        raise ValueError("paid_at must be timezone-aware")

    if billing_interval == "month":
        month_index = paid_at.month  # 1-based month after the current one
        year = paid_at.year + (1 if month_index == 12 else 0)
        month = 1 if month_index == 12 else month_index + 1
    elif billing_interval == "year":
        year = paid_at.year + 1
        month = paid_at.month
    else:
        raise ValueError("billing_interval must be 'month' or 'year'")

    day = min(paid_at.day, calendar.monthrange(year, month)[1])
    return paid_at.replace(year=year, month=month, day=day)
