
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
