"""Grader-side reference implementation of docs/proration.md (never shipped to /app).

Used to compute expected values for the held-out cases. Independent of the
code under test: it does not import anything from /app.
"""
from __future__ import annotations

import calendar as _cal
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

MONTHS = {"month": 1, "year": 12}


def add_months(anchor: date, n: int) -> date:
    total = anchor.month - 1 + n
    y = anchor.year + total // 12
    m = total % 12 + 1
    return date(y, m, min(anchor.day, _cal.monthrange(y, m)[1]))


def cycle_bounds(anchor: date, on: date, interval: str):
    step = MONTHS[interval]
    k = ((on.year - anchor.year) * 12 + (on.month - anchor.month)) // step
    k = max(k, 0)
    while add_months(anchor, k * step) > on:
        k -= 1
    while add_months(anchor, (k + 1) * step) <= on:
        k += 1
    return add_months(anchor, k * step), add_months(anchor, (k + 1) * step)


def portion(amount: int, num: int, den: int) -> int:
    exact = Decimal(amount) * Decimal(num) / Decimal(den)
    return int(exact.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def price_on(plan: dict, on: date) -> int:
    cur = None
    for p in sorted(plan["prices"], key=lambda p: p["effective_from"]):
        if date.fromisoformat(p["effective_from"]) <= on:
            cur = int(p["unit_amount"])
    if cur is None:
        raise LookupError("no price")
    return cur


def prorate(plans: dict, old_id: str, anchor: date, new_id: str, change_at: date) -> dict:
    old, new = plans[old_id], plans[new_id]
    start, end = cycle_bounds(anchor, change_at, old["interval"])
    period_days = (end - start).days
    remaining = (end - change_at).days
    credit = portion(price_on(old, start), remaining, period_days)
    if old["interval"] == new["interval"]:
        charge = portion(price_on(new, change_at), remaining, period_days)
        new_anchor, next_renewal = anchor, end
    else:
        charge = price_on(new, change_at)
        new_anchor = change_at
        next_renewal = add_months(change_at, MONTHS[new["interval"]])
    return {
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "credit": credit,
        "charge": charge,
        "total": charge - credit,
        "new_anchor": new_anchor.isoformat(),
        "next_renewal": next_renewal.isoformat(),
    }
