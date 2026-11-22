# feedsync

Keeps the shop catalog (`data/catalog.db`, SQLite) in step with Kestrel
Wholesale's product/price feed. Since FEED-402 we consume the supplier's v2
**delta** API instead of the nightly full CSV dump; the API contract is in
`docs/feed_api.md`.

## Layout

| path | what |
|---|---|
| `feedsync/client.py` | HTTP client for `/v2/changes` (pagination, local test feed start-up) |
| `feedsync/sync.py` | applies delta pages to the catalog |
| `feedsync/store.py` | SQLite schema, product writes, sync state, effective prices |
| `feedsync/cli.py` | `python -m feedsync sync / report / status / price / overrides` |
| `dev/feedstub.py` | local stand-in for the supplier feed, serving `dev/feed_data/` |
| `tests/test_sync.py` | black-box tests (CLI against the stub) |

## Running

    python -m feedsync sync              # apply the feed to data/catalog.db
    python -m feedsync status            # cursor, product count, last sync
    python -m feedsync report [--json]   # feed / override / effective price per SKU
    python -m feedsync price KS-10007    # one SKU
    python -m feedsync overrides prune-expired   # delete overrides whose end date has passed
    python -m feedsync overrides end KS-10007    # catalog admins: end an override early (promo pulled, SKU retired)
    python -m unittest discover -s tests -v

Settings live in `feedsync.toml`; `FEED_URL` and `FEEDSYNC_DB` override them.

### Local test feed

`feedsync.toml` points at the local test feed on `http://127.0.0.1:8765`.
When the feed URL is on 127.0.0.1 and nothing is listening, `feedsync sync`
starts `dev/feedstub.py` in the background for you. You can also run it by
hand: `python dev/feedstub.py --port 8765`. It serves `dev/feed_data/` (a copy
of a recent production delta) and logs every request it gets to
`/var/tmp/feedstub/requests.log`.

## Tables

- `products` (sku, title, price_cents, currency, updated_at, feed_seq): owned
  by the sync. The storefront export reads this table directly, so keep the
  column names; there must be one row per SKU.
- `sync_state` (key, value): the feed cursor (`feed_cursor`) and `last_sync_at`.
- `price_overrides`: manual promo/clearance prices maintained by the
  merchandising team through their admin tool (author/reason on every row).
  An override is active from `starts_on` to `ends_on` inclusive (`ends_on`
  NULL = open-ended); the newest active one wins. Effective price = active
  override, else the feed price. `report --json` is what the storefront price
  export consumes.

Prices are integer cents everywhere in the database.
