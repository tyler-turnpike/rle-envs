**FEED-412 / FEED-418: finish the v2 delta sync**

We cut the catalog over from the nightly CSV dump to Kestrel's v2 delta feed (FEED-402), but the sync in `/app/feedsync` was never finished and the catalog it produces is wrong. From what I've seen running it against the local test feed: some products show up twice in `feedsync report`, products the supplier dropped never go away, a handful of prices are a cent off, products added near the end of the delta are missing, and every run starts again from the beginning of the feed.

Please fix it so that:

- `python -m feedsync sync` brings `data/catalog.db` to the feed's current state: one row per SKU, exact prices, deletions applied.
- A second run is incremental: it resumes from the stored cursor and doesn't re-download pages it already applied.
- `python -m feedsync report` shows the right effective prices (active merchandising override where there is one, feed price otherwise).

The feed contract is in `docs/feed_api.md` and the README explains the local test feed (`dev/feedstub.py`; the CLI starts it for you). The tests in `tests/` should pass when you're done. Once it works, run the sync against the local test feed so `data/catalog.db` is current, and give me a short summary of what was wrong and anything I should know.
