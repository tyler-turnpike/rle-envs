"""Order pricing and receipts."""
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from .codec import OrderError, dump_receipt, load_receipt, parse_batch, parse_order

CENT = Decimal("0.01")


def money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def price_order(order):
    """Subtotal, per-line tax (rounded per line), discount and total, all exact."""
    subtotal = sum((line["unit_price"] * line["qty"] for line in order["lines"]), Decimal("0"))
    tax = sum((money(line["unit_price"] * line["qty"] * line["tax_rate"]) for line in order["lines"]),
              Decimal("0"))
    discount = min(money(order["discount"]), money(subtotal))
    total = money(subtotal) + tax - discount
    return {"order_id": order["order_id"], "currency": order["currency"],
            "subtotal": money(subtotal), "tax": money(tax), "discount": discount,
            "total": money(total), "line_count": len(order["lines"])}


def receipt_for(text):
    return dump_receipt(price_order(parse_order(text)))


def summarize_batch(text):
    """Totals per currency for a JSON-lines export, plus the lines that were rejected."""
    orders, errors = parse_batch(text)
    totals = defaultdict(lambda: Decimal("0"))
    for order in orders:
        totals[order["currency"]] += price_order(order)["total"]
    return {"orders": len(orders), "totals": {c: money(v) for c, v in sorted(totals.items())},
            "rejected": errors}


def store_receipts(text, out_dir):
    """Write one receipt per valid order; returns the ids written."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    orders, _ = parse_batch(text)
    written = []
    for order in orders:
        receipt = price_order(order)
        (out / f"{receipt['order_id']}.json").write_text(dump_receipt(receipt) + "\n")
        written.append(receipt["order_id"])
    return written


def reload_total(path):
    receipt = load_receipt(Path(path).read_text())
    if "total" not in receipt:
        raise OrderError(f"{path}: not a receipt")
    return Decimal(str(receipt["total"]))
