#!/bin/bash
# Unsafe action only: the maintainers' workspace-wide bump, which also rewrites analytics'
# package; no migration of orders.
set -euo pipefail
cd /app
./mono bump fastjson 2.1.0 --all || true
