"""feedsync command line.

    python -m feedsync sync            apply the supplier's delta feed to the catalog
    python -m feedsync report [--json] catalog with feed, override and effective prices
    python -m feedsync status          cursor, product count, last sync
    python -m feedsync price SKU       effective price of one SKU and where it comes from

Settings come from feedsync.toml; FEED_URL and FEEDSYNC_DB override the feed
URL and the catalog path.
"""
import argparse
import json
import logging
import os
import sys
import tomllib
from pathlib import Path

from . import store
from .client import FeedClient, FeedError, ensure_local_feed
from .sync import CURSOR_KEY, run_sync

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "feedsync.toml"


def load_config(path):
    path = Path(path)
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)
    feed, catalog = raw.get("feed", {}), raw.get("catalog", {})
    db_path = Path(os.environ.get("FEEDSYNC_DB") or catalog.get("path", "data/catalog.db"))
    if not db_path.is_absolute():
        db_path = path.parent / db_path
    return {"feed_url": os.environ.get("FEED_URL") or feed["url"],
            "page_size": int(feed.get("page_size", 25)),
            "timeout": float(feed.get("timeout_sec", 10)),
            "db_path": str(db_path)}


def cmd_sync(cfg, args):
    ensure_local_feed(cfg["feed_url"])
    client = FeedClient(cfg["feed_url"], page_size=cfg["page_size"], timeout=cfg["timeout"])
    conn = store.connect(cfg["db_path"])
    try:
        stats = run_sync(conn, client)
    finally:
        conn.close()
    print(json.dumps(stats))
    return 0


def cmd_report(cfg, args):
    conn = store.connect(cfg["db_path"])
    rows = store.report_rows(conn, args.date)
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    print(f"{'SKU':<10} {'feed':>9} {'override':>9} {'effective':>9}  title")
    for r in rows:
        print(f"{r['sku']:<10} {r['feed_price']:>9} {r['override_price'] or '-':>9} "
              f"{r['effective_price']:>9}  {r['title']}")
    print(f"{len(rows)} products")
    return 0


def cmd_status(cfg, args):
    conn = store.connect(cfg["db_path"])
    active = sum(1 for r in conn.execute("SELECT DISTINCT sku FROM price_overrides")
                 if store.active_override(conn, r["sku"]) is not None)
    print(f"feed:        {cfg['feed_url']}")
    print(f"catalog:     {cfg['db_path']}")
    print(f"cursor:      {store.get_state(conn, CURSOR_KEY) or '-'}")
    print(f"last sync:   {store.get_state(conn, 'last_sync_at') or 'never'}")
    print(f"products:    {store.product_count(conn)}")
    print(f"overrides:   {active} active")
    return 0


def cmd_price(cfg, args):
    conn = store.connect(cfg["db_path"])
    cents, source = store.effective_price(conn, args.sku, args.date)
    if cents is None:
        print(f"{args.sku}: not in catalog", file=sys.stderr)
        return 1
    detail = ""
    if source == "override":
        o = store.active_override(conn, args.sku, args.date)
        detail = f" (override by {o['author']}: {o['reason']})"
    print(f"{args.sku}: {store.format_cents(cents)} [{source}]{detail}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="feedsync")
    ap.add_argument("--config", default=os.environ.get("FEEDSYNC_CONFIG", str(DEFAULT_CONFIG)))
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("sync")
    rep = sub.add_parser("report")
    rep.add_argument("--json", action="store_true")
    rep.add_argument("--date", help="evaluate overrides on this day (YYYY-MM-DD)")
    sub.add_parser("status")
    pr = sub.add_parser("price")
    pr.add_argument("sku")
    pr.add_argument("--date")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    cfg = load_config(args.config)
    handler = {"sync": cmd_sync, "report": cmd_report, "status": cmd_status, "price": cmd_price}
    try:
        return handler[args.command](cfg, args)
    except FeedError as exc:
        print(f"feed error: {exc}", file=sys.stderr)
        return 2
