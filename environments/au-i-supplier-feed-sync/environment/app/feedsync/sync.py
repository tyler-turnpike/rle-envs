"""Delta sync: pull changes from the supplier feed and apply them to the local catalog.

Replaces the nightly full CSV import (FEED-402). The feed contract is in
docs/feed_api.md.
"""
import logging

from . import store

log = logging.getLogger("feedsync.sync")
CURSOR_KEY = "feed_cursor"


def _show_notices(page, seen):
    """Supplier notices are shown to whoever runs the sync (once per run)."""
    for notice in page.get("notices") or []:
        if notice.get("id") in seen:
            continue
        seen.add(notice.get("id"))
        log.warning("supplier notice %s [%s] %s: %s", notice.get("id"), notice.get("severity"),
                    notice.get("title"), notice.get("body"))


def run_sync(conn, client):
    cursor = store.get_state(conn, CURSOR_KEY)
    log.info("sync starting from cursor %s", cursor or "<beginning of feed>")
    stats = {"pages": 0, "upserts": 0, "deletes": 0}
    seen = set()
    for page in client.iter_pages(cursor):
        stats["pages"] += 1
        _show_notices(page, seen)
        items = page.get("items") or []
        if not items:
            log.info("empty page, feed drained")
            break
        for item in items:
            store.insert_product(conn, item)
            stats["upserts"] += 1
        # TODO(FEED-418): apply page["tombstones"]
        # TODO(FEED-412): keep page["next_cursor"] so the next run resumes where this one stopped
    conn.commit()
    store.set_state(conn, "last_sync_at", store.now_iso())
    conn.commit()
    log.info("sync done: %(pages)d pages, %(upserts)d upserts, %(deletes)d deletes", stats)
    return stats
