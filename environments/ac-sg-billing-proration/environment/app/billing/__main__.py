"""Command line: preview the invoice for a plan change.

    python -m billing preview --sub data/subscriptions.json --id sub_1042 \
        --to pro-monthly --at 2026-01-31 [--json]
"""
from __future__ import annotations

import argparse
import json
import sys

from .calendar import parse_date
from .catalog import DEFAULT_CATALOG, load_catalog
from .invoice import build_preview, render_text, to_dict
from .proration import Subscription, prorate_change


def _load_subscription(path: str, sub_id: str) -> tuple[Subscription, int]:
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)["subscriptions"]
    for row in rows:
        if row["id"] == sub_id:
            sub = Subscription(row["id"], row["customer"], row["plan"], parse_date(row["anchor"]))
            return sub, int(row.get("balance", 0))
    raise SystemExit(f"no subscription {sub_id} in {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="billing")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("preview", help="preview a mid-cycle plan change")
    p.add_argument("--sub", required=True, help="subscriptions JSON file")
    p.add_argument("--id", required=True, help="subscription id")
    p.add_argument("--to", required=True, help="new plan id")
    p.add_argument("--at", required=True, help="change date, YYYY-MM-DD")
    p.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    p.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    catalog = load_catalog(args.catalog)
    subscription, balance = _load_subscription(args.sub, args.id)
    proration = prorate_change(subscription, args.to, parse_date(args.at), catalog)
    currency = catalog.plan(args.to).currency
    preview = build_preview(proration, currency, balance_before=balance)
    if args.json:
        json.dump(to_dict(preview), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(render_text(preview))
    return 0


if __name__ == "__main__":
    sys.exit(main())
