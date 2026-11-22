#!/usr/bin/env bash
# teardown.sh - remove a preview environment's cloud resources.
#
#   ./teardown.sh <env> [--dry-run]
#
# <env> is a preview env from conf/previews.conf (e.g. pr-482). Resources are
# found with the env's label selector and deleted through cloudctl.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/inventory.sh
source "$ROOT/lib/inventory.sh"
# shellcheck source=lib/order.sh
source "$ROOT/lib/order.sh"
# shellcheck source=lib/report.sh
source "$ROOT/lib/report.sh"

usage() {
    echo "usage: $0 <env> [--dry-run]" >&2
    exit 2
}

[[ $# -ge 1 ]] || usage
ENV_ARG="$1"; shift
DRY_RUN=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        *) usage ;;
    esac
done

load_env_config "$ENV_ARG"
echo "teardown: env=$ENV_NAME project=$ENV_PROJECT selector=$ENV_SELECTOR"

inventory="$(inventory_collect "$ENV_SELECTOR")"
echo "teardown: $(printf '%s\n' "$inventory" | grep -c . || true) resource(s) found"

# TODO(PLAT-311): volumes have to be detached before they can be deleted.
# TODO(PLAT-311): make re-runs safe and write the report (lib/report.sh).
printf '%s\n' "$inventory" | order_resources | while IFS=$'\t' read -r id kind name; do
    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "would delete $kind $id ($name)"
        continue
    fi
    echo "deleting $kind $id ($name)"
    "$CLOUDCTL" delete "$id"
done

echo "teardown: done"
