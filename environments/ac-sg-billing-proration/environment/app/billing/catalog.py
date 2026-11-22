"""Plan catalog: plan definitions and their price history."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple

from .calendar import interval_months, parse_date

DEFAULT_CATALOG = Path(__file__).resolve().parent.parent / "data" / "catalog.json"


@dataclass(frozen=True)
class Plan:
    plan_id: str
    name: str
    interval: str
    currency: str
    # (effective_from, unit price in minor units), sorted by date
    prices: Tuple[Tuple[date, int], ...] = field(default_factory=tuple)

    @property
    def months(self) -> int:
        return interval_months(self.interval)

    def price_on(self, on: date) -> int:
        """Price in force on ``on`` (the latest entry whose start is <= on)."""
        current = None
        for start, cents in self.prices:
            if start <= on:
                current = cents
            else:
                break
        if current is None:
            raise LookupError(f"plan {self.plan_id} has no price on {on}")
        return current


class Catalog:
    def __init__(self, plans: Dict[str, Plan]):
        self._plans = dict(plans)

    def plan(self, plan_id: str) -> Plan:
        try:
            return self._plans[plan_id]
        except KeyError:
            raise KeyError(f"unknown plan: {plan_id}") from None

    def price(self, plan_id: str, on: date) -> int:
        return self.plan(plan_id).price_on(on)

    def plan_ids(self) -> List[str]:
        return sorted(self._plans)

    def __contains__(self, plan_id: str) -> bool:
        return plan_id in self._plans


def _plan_from_dict(raw: dict) -> Plan:
    history = sorted(
        (parse_date(p["effective_from"]), int(p["unit_amount"])) for p in raw["prices"]
    )
    if not history:
        raise ValueError(f"plan {raw['id']} has an empty price history")
    if raw["interval"] not in ("month", "year"):
        raise ValueError(f"plan {raw['id']} has unknown interval {raw['interval']!r}")
    return Plan(
        plan_id=raw["id"],
        name=raw.get("name", raw["id"]),
        interval=raw["interval"],
        currency=raw.get("currency", "USD"),
        prices=tuple(history),
    )


def load_catalog(path: Path | str = DEFAULT_CATALOG) -> Catalog:
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    plans = {}
    for raw in doc["plans"]:
        plan = _plan_from_dict(raw)
        if plan.plan_id in plans:
            raise ValueError(f"duplicate plan id {plan.plan_id}")
        plans[plan.plan_id] = plan
    return Catalog(plans)
