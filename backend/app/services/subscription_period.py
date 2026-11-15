"""Fixed-duration subscription periods anchored to verified payment timestamps."""

import calendar
from datetime import datetime, timedelta


def subscription_period_end(paid_at: datetime, billing_interval: str) -> datetime:
    """Return the end of a paid period from an aware payment timestamp.

    Monthly billing is exactly 30 * 24 hours, independent of calendar month
    length. Annual billing remains one calendar year, clamped to the final
    valid day when needed. The original timezone and wall-clock time are kept.
    """
    if paid_at.tzinfo is None or paid_at.utcoffset() is None:
        raise ValueError("paid_at must be timezone-aware")

    if billing_interval == "month":
        return paid_at + timedelta(days=30)

    if billing_interval == "year":
        year = paid_at.year + 1
        day = min(paid_at.day, calendar.monthrange(year, paid_at.month)[1])
        return paid_at.replace(year=year, day=day)

    raise ValueError("billing_interval must be 'month' or 'year'")
