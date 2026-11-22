"""Daily revenue ledger built from the orders receipt export (analytics team).

The ledger feeds finance's month-end close, so every figure must be exact to the cent.
"""
from collections import defaultdict
from decimal import Decimal

import fastjson


def read_receipts(text):
    """Receipts export: one JSON receipt per line, each with a `day` field added by the exporter."""
    rows = []
    for raw in text.splitlines():
        if raw.strip():
            rows.append(fastjson.loads(raw))
    return rows


def _amount(value):
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str):
        return Decimal(value)
    return Decimal(repr(value))


def daily_ledger(text):
    days = defaultdict(lambda: {"orders": 0, "revenue": Decimal("0"), "tax": Decimal("0")})
    for row in read_receipts(text):
        day = days[row["day"]]
        day["orders"] += 1
        day["revenue"] += _amount(row["total"])
        day["tax"] += _amount(row["tax"])
    return {d: days[d] for d in sorted(days)}


def average_ticket(text):
    rows = read_receipts(text)
    if not rows:
        return Decimal("0")
    total = sum((_amount(r["total"]) for r in rows), Decimal("0"))
    return (total / len(rows)).quantize(Decimal("0.01"))


def ledger_json(text):
    return fastjson.dumps(daily_ledger(text), sort_keys=True, indent=2)
