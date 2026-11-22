"""Order JSON codec: incoming order documents and the receipts we store.

Amounts are exact (Decimal) end to end; receipts are canonical JSON (sorted keys,
amounts written as strings) because finance diffs them across releases.
"""
from decimal import Decimal

import fastjson

REQUIRED = ("order_id", "currency", "lines")
LINE_FIELDS = ("sku", "qty", "unit_price")


class OrderError(ValueError):
    """The document is not a valid order."""


def parse_order(text):
    try:
        doc = fastjson.loads(text)
    except fastjson.JSONError as exc:
        raise OrderError(f"malformed order JSON: {exc}") from None
    if not isinstance(doc, dict):
        raise OrderError("order must be a JSON object")
    missing = [k for k in REQUIRED if k not in doc]
    if missing:
        raise OrderError(f"order missing {', '.join(missing)}")
    lines = []
    for i, line in enumerate(doc["lines"]):
        if not isinstance(line, dict) or any(k not in line for k in LINE_FIELDS):
            raise OrderError(f"line {i} needs {', '.join(LINE_FIELDS)}")
        price = line["unit_price"]
        if not isinstance(price, Decimal):
            price = Decimal(str(price))
        lines.append({"sku": str(line["sku"]), "qty": int(line["qty"]), "unit_price": price,
                      "tax_rate": Decimal(str(line.get("tax_rate", "0")))})
    discount = doc.get("discount", Decimal("0"))
    return {"order_id": str(doc["order_id"]), "currency": str(doc["currency"]).upper(),
            "lines": lines, "discount": Decimal(str(discount))}


def parse_batch(text):
    """Parse a JSON-lines export; returns (orders, errors) so one bad line does not stop a batch."""
    orders, errors = [], []
    for n, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            orders.append(parse_order(raw))
        except OrderError as exc:
            errors.append(f"line {n}: {exc}")
    return orders, errors


def dump_receipt(receipt):
    return fastjson.dumps(receipt, sort_keys=True)


def load_receipt(text):
    try:
        return fastjson.loads(text)
    except fastjson.JSONError as exc:
        raise OrderError(f"malformed receipt: {exc}") from None
