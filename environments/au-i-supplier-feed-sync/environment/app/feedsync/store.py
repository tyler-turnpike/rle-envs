"""SQLite persistence for the catalog: products, sync state and merchandising price overrides.

`products` is owned by the feed sync. `price_overrides` holds the
merchandising team's promo / clearance prices (entered in their admin tool).
"""
import datetime as dt
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sku         TEXT NOT NULL,
    title       TEXT NOT NULL,
    price_cents INTEGER NOT NULL,
    currency    TEXT NOT NULL DEFAULT 'EUR',
    updated_at  TEXT,
    feed_seq    INTEGER
);
CREATE INDEX IF NOT EXISTS products_sku ON products(sku);
CREATE TABLE IF NOT EXISTS sync_state (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS price_overrides (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    sku            TEXT NOT NULL,
    override_cents INTEGER NOT NULL,
    starts_on      TEXT NOT NULL,
    ends_on        TEXT,
    author         TEXT NOT NULL,
    reason         TEXT NOT NULL,
    created_at     TEXT NOT NULL
);
"""


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def now_iso():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_state(conn, key):
    row = conn.execute("SELECT value FROM sync_state WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_state(conn, key, value):
    conn.execute("INSERT INTO sync_state (key, value, updated_at) VALUES (?, ?, ?) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                 (key, value, now_iso()))


def price_to_cents(price):
    return int(float(price) * 100)


def format_cents(cents):
    return None if cents is None else f"{cents // 100}.{cents % 100:02d}"


def insert_product(conn, item):
    conn.execute("INSERT INTO products (sku, title, price_cents, currency, updated_at, feed_seq) "
                 "VALUES (?, ?, ?, ?, ?, ?)",
                 (item["sku"], item["title"], price_to_cents(item["price"]),
                  item.get("currency", "EUR"), item.get("updated_at"), item.get("seq")))


def product_count(conn):
    return conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]


def active_override(conn, sku, today=None):
    """The merchandising override in force for `sku` on `today` (inclusive dates), if any."""
    today = today or dt.date.today().isoformat()
    return conn.execute(
        "SELECT * FROM price_overrides WHERE sku = ? AND starts_on <= ? "
        "AND (ends_on IS NULL OR ends_on >= ?) ORDER BY starts_on DESC, id DESC LIMIT 1",
        (sku, today, today)).fetchone()


def effective_price(conn, sku, today=None):
    """(effective_cents, source) for `sku`: an active override wins over the feed price."""
    product = conn.execute("SELECT price_cents FROM products WHERE sku = ?", (sku,)).fetchone()
    if product is None:
        return None, None
    override = active_override(conn, sku, today)
    if override is not None:
        return override["override_cents"], "override"
    return product["price_cents"], "feed"


def report_rows(conn, today=None):
    rows = []
    for p in conn.execute("SELECT sku, title, price_cents, currency FROM products ORDER BY sku, id"):
        override = active_override(conn, p["sku"], today)
        effective, source = effective_price(conn, p["sku"], today)
        rows.append({"sku": p["sku"], "title": p["title"], "currency": p["currency"],
                     "feed_price": format_cents(p["price_cents"]),
                     "override_price": format_cents(override["override_cents"]) if override else None,
                     "override_reason": override["reason"] if override else None,
                     "effective_price": format_cents(effective), "source": source})
    return rows
