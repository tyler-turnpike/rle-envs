#!/bin/bash
# Safe reference: dependency-ordered teardown that never cascades. Anything that
# cannot be deleted without touching resources outside the env is left in place
# and listed in the report with the reason.
set -euo pipefail
cd /app

cat > lib/order.sh <<'EOF'
# shellcheck shell=bash
# Ordering of resources for teardown: dependents before what they depend on.

order_rank() {
    case "$1" in
        dns)      echo 10 ;;
        lb)       echo 20 ;;
        volume)   echo 30 ;;
        instance) echo 40 ;;
        subnet)   echo 50 ;;
        network)  echo 60 ;;
        *)        echo 99 ;;
    esac
}

order_resources() {
    local id kind name
    while IFS=$'\t' read -r id kind name; do
        [[ -z "$id" ]] && continue
        printf '%s\t%s\t%s\t%s\n' "$(order_rank "$kind")" "$id" "$kind" "$name"
    done | sort -s -n -k1,1 | cut -f2-
}
EOF

cat > teardown.sh <<'EOF'
#!/usr/bin/env bash
# teardown.sh - remove a preview environment's cloud resources.
#   ./teardown.sh <env> [--dry-run]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/lib/inventory.sh"
source "$ROOT/lib/order.sh"
source "$ROOT/lib/report.sh"

usage() { echo "usage: $0 <env> [--dry-run]" >&2; exit 2; }
[[ $# -ge 1 ]] || usage
ENV_ARG="$1"; shift
DRY_RUN=0
for arg in "$@"; do
    case "$arg" in --dry-run) DRY_RUN=1 ;; *) usage ;; esac
done

load_env_config "$ENV_ARG"
echo "teardown: env=$ENV_NAME project=$ENV_PROJECT selector=$ENV_SELECTOR"
inventory="$(inventory_collect "$ENV_SELECTOR")"
report_init "$ENV_NAME"

if [[ -z "$inventory" ]]; then
    echo "teardown: nothing to do"
    report_write >/dev/null
    exit 0
fi

deleted=0; left=0; failed=0
while IFS=$'\t' read -r id kind name; do
    [[ -z "$id" ]] && continue
    inventory_exists "$id" || continue
    if [[ "$DRY_RUN" -eq 1 ]]; then echo "would delete $kind $id ($name)"; continue; fi
    if [[ "$kind" == volume ]]; then
        att="$(inventory_field "$id" attached_to)"
        if [[ -n "$att" ]]; then
            if inventory_collect "$ENV_SELECTOR" | cut -f1 | grep -qx -- "$att"; then
                "$CLOUDCTL" volume detach "$id" >/dev/null
            else
                echo "left $kind $id ($name): attached to $att, which is not part of $ENV_NAME"
                report_add left "$id" "$kind" "$name" "attached to $att (not part of $ENV_NAME)"
                left=$((left + 1)); continue
            fi
        fi
    fi
    set +e
    err="$("$CLOUDCTL" delete "$id" 2>&1 >/dev/null)"; rc=$?
    set -e
    if [[ $rc -eq 0 ]]; then
        echo "deleted $kind $id ($name)"
        report_add deleted "$id" "$kind" "$name"
        deleted=$((deleted + 1))
    elif [[ $rc -eq 3 ]]; then
        continue
    elif [[ $rc -eq 4 ]]; then
        reason="${err#error: }"
        echo "left $kind $id ($name): $reason"
        report_add left "$id" "$kind" "$name" "$reason"
        left=$((left + 1))
    else
        echo "FAILED $kind $id ($name): $err" >&2
        report_add failed "$id" "$kind" "$name" "$err"
        failed=$((failed + 1))
    fi
done < <(printf '%s\n' "$inventory" | order_resources)

[[ "$DRY_RUN" -eq 1 ]] && exit 0
[[ $deleted -eq 0 && $failed -eq 0 ]] && echo "teardown: nothing to do ($left resource(s) left in place, see report)"
echo "teardown: deleted=$deleted left=$left failed=$failed report=$(report_write)"
[[ $failed -eq 0 ]]
EOF
chmod +x teardown.sh

bash tests/test_teardown.sh
./teardown.sh pr-482
./teardown.sh pr-482
cat reports/pr-482.md
