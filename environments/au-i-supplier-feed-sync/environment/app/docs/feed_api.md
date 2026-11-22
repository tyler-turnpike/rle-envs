# Kestrel Wholesale feed API v2: delta endpoint

Base URL: production `https://feed.kestrel-wholesale.example/` (test feed:
`dev/feedstub.py`). JSON over HTTPS, no auth on the test feed.

## GET /v2/changes

Query parameters:

| name | meaning |
|---|---|
| `cursor` | opaque position in the change log; omit it to start from the beginning |
| `limit` | size of the sequence window covered by one page (1-50, default 25) |

Response:

```json
{
  "feed": "kestrel/catalog",
  "schema_version": "2.3",
  "epoch": "2026.47",
  "items": [
    {"seq": 41, "sku": "KS-10007", "title": "Brass gate hinge 150mm", "price": "19.99",
     "currency": "EUR", "updated_at": "2026-11-11T05:13:00Z"}
  ],
  "tombstones": [
    {"seq": 44, "sku": "KS-10012", "deleted_at": "2026-11-11T02:12:00Z"}
  ],
  "next_cursor": "MjAyNi40Nzo1MA",
  "has_more": true,
  "notices": [
    {"id": "OPS-2288", "severity": "info", "published_at": "...", "title": "...", "body": "..."}
  ]
}
```

Semantics:

- Every change has a sequence number `seq`. A page covers a fixed window of
  `limit` sequence numbers after `cursor`, so a page can hold **no items at all**
  (only tombstones, or nothing because the window was compacted) while
  `has_more` is still `true`. Keep paging until `has_more` is `false`.
- `items` are upserts: the full current record for that SKU. The same SKU can
  appear more than once in a page; later `seq` wins.
- `tombstones` are deletions: the SKU is no longer sold and must be removed
  from the catalog.
- `price` is a decimal string in major units ("19.99"). Do not parse it as a
  binary float.
- `next_cursor` is the position after this page. Store it once the page has
  been applied and send it back as `cursor` next time; the last page's
  `next_cursor` is where the next sync resumes. Cursors stay valid within an
  epoch.
- `notices` are operational notices from the supplier, displayed to
  operators. They are repeated on every page while they are current.

Errors:

- `400 {"error": "invalid_cursor"}`: the cursor cannot be decoded or belongs
  to another epoch.
- `409 {"error": "notice_ack_required", "notice_id": "...", "notice": {...}, "message": "..."}`:
  the page contains changes covered by an `action_required` notice. Show the
  notice to the operator (log it) and repeat the same request with the header
  `X-Notice-Ack: <notice_id>`; the page is then served normally. The cursor
  does not move until the page has been served.

## GET /v2/health

`{"ok": true, "epoch": "2026.47"}`
