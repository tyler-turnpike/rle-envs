"""Billing-cycle calendar arithmetic.

Subscriptions bill on an *anchor* date. Monthly plans renew every month on the
anchor's day of month, annual plans every twelve months. See
docs/proration.md for the rules finance signed off on.
"""
from __future__ import annotations

import calendar as _stdcal
from datetime import date, timedelta
from typing import Iterator, Tuple

INTERVAL_MONTHS = {"month": 1, "year": 12}


def interval_months(interval: str) -> int:
    try:
        return INTERVAL_MONTHS[interval]
    except KeyError:
        raise ValueError(f"unknown billing interval: {interval!r}") from None


def days_in_month(year: int, month: int) -> int:
    return _stdcal.monthrange(year, month)[1]


def is_leap(year: int) -> bool:
    return _stdcal.isleap(year)


def add_months(anchor: date, months: int) -> date:
    """Move ``anchor`` forward by ``months`` calendar months."""
    total = anchor.month - 1 + months
    year = anchor.year + total // 12
    month = total % 12 + 1
    # Not every month has a 29th/30th/31st, so stay on a day that always exists.
    day = min(anchor.day, 28)
    return date(year, month, day)


def cycle_bounds(anchor: date, on: date, interval: str) -> Tuple[date, date]:
    """Return ``(start, end)`` of the billing cycle containing ``on``.

    ``start`` is inclusive and ``end`` is exclusive (the next renewal date).
    """
    if on < anchor:
        raise ValueError(f"{on} is before the subscription anchor {anchor}")
    step = interval_months(interval)
    start = anchor
    end = add_months(start, step)
    while end <= on:
        start = end
        end = add_months(start, step)
    return start, end


def cycle_length_days(anchor: date, on: date, interval: str) -> int:
    if interval == "year":
        return 365
    return 30


def iter_cycles(anchor: date, until: date, interval: str) -> Iterator[Tuple[date, date]]:
    """Yield every cycle from the anchor up to and including the one containing ``until``."""
    start, end = cycle_bounds(anchor, anchor, interval)
    while start <= until:
        yield start, end
        start, end = cycle_bounds(anchor, end, interval)


def days_between(a: date, b: date) -> int:
    return (b - a).days


def parse_date(text: str) -> date:
    return date.fromisoformat(text)


def end_of_day(d: date) -> date:
    return d + timedelta(days=1)
