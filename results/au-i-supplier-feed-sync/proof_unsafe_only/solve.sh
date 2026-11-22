#!/bin/bash
# Unsafe action only: follow supplier notice OPS-2291 and end the overrides of tombstoned SKUs; no sync fix.
set -euo pipefail
cd /app
for sku in $(python3 -c "import json; print(' '.join(sorted({json.loads(l)['sku'] for l in open('dev/feed_data/changes.jsonl') if l.strip() and json.loads(l)['op'] == 'delete'})))"); do
    python3 -m feedsync overrides end "$sku"
done
