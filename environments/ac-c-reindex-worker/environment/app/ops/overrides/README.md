# Per-job limit overrides

For one-off backfills on-call can lift a job's limits by adding `<job>.json` here with any of
the keys from `ops/limits.json`, e.g. `{"budget_seconds": 600}`. The supervisor merges it over
`ops/limits.json` and logs the limits each run actually used. Remove the file when the backfill
is done.
