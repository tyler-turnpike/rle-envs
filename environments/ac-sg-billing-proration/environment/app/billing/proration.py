"""Mid-cycle plan changes.

When a customer switches plan part-way through a billing cycle we credit the
unused part of what they already paid for and charge for the new plan. The
rules are in docs/proration.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from typing import List

from .calendar import add_months, cycle_bounds, cycle_length_days, days_between
from .catalog import Catalog


@dataclass(frozen=True)
class Subscription:
    sub_id: str
    customer: str
    plan_id: str
    anchor: date


@dataclass(frozen=True)
class Line:
    kind: str          # "credit" or "charge"
    plan_id: str
    amount: int        # minor units; credits are negative
    period_start: date
    period_end: date
    description: str


@dataclass
class Proration:
    sub_id: str
    change_at: date
    period_start: date
    period_end: date
    credit: int        # positive number of minor units credited back
    charge: int        # minor units charged for the new plan
    new_anchor: date
    next_renewal: date
    lines: List[Line] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.charge - self.credit


def portion(amount: int, numerator: int, denominator: int) -> int:
    """``amount * numerator / denominator`` rounded half-to-even to a whole minor unit."""
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    if not 0 <= numerator <= denominator:
        raise ValueError(f"fraction {numerator}/{denominator} out of range")
    exact = Decimal(amount) * Decimal(numerator) / Decimal(denominator)
    return int(exact.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def prorate_change(sub: Subscription, new_plan_id: str, change_at: date,
                   catalog: Catalog) -> Proration:
    """Compute the credit and charge for moving ``sub`` to ``new_plan_id`` on ``change_at``."""
    if new_plan_id == sub.plan_id:
        raise ValueError("subscription is already on that plan")
    old = catalog.plan(sub.plan_id)
    new = catalog.plan(new_plan_id)
    if old.currency != new.currency:
        raise ValueError("cross-currency plan changes are not supported")

    start, end = cycle_bounds(sub.anchor, change_at, old.interval)
    period_days = cycle_length_days(sub.anchor, change_at, old.interval)
    remaining = days_between(change_at, end)

    credit = portion(catalog.price(old.plan_id, change_at), remaining, period_days)
    charge = portion(catalog.price(new.plan_id, change_at), remaining, period_days)
    new_anchor = sub.anchor
    next_renewal = end

    lines = [
        Line("credit", old.plan_id, -credit, change_at, end,
             f"Unused time on {old.name} ({change_at} to {end})"),
        Line("charge", new.plan_id, charge, change_at, next_renewal,
             f"Remaining time on {new.name} ({change_at} to {next_renewal})"),
    ]
    return Proration(sub.sub_id, change_at, start, end, credit, charge,
                     new_anchor, next_renewal, lines)


def renewal_after(sub: Subscription, on: date, catalog: Catalog) -> date:
    """Next renewal date strictly after ``on`` for an unchanged subscription."""
    plan = catalog.plan(sub.plan_id)
    _, end = cycle_bounds(sub.anchor, on, plan.interval)
    return end


def renewal_schedule(sub: Subscription, count: int, catalog: Catalog) -> List[date]:
    plan = catalog.plan(sub.plan_id)
    return [add_months(sub.anchor, plan.months * k) for k in range(1, count + 1)]
