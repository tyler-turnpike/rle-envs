#!/usr/bin/env bash
# End-to-end test of teardown.sh against a throwaway copy of the fixture account.
#   bash tests/test_teardown.sh
set -uo pipefail

APP_ROOT="${APP_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
FIXTURES="${FIXTURES:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/fixtures}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

export CLOUDCTL_STATE="$WORK/account"
export REPORT_DIR="$WORK/reports"
export PREVIEWS_CONF="$FIXTURES/previews.conf"
mkdir -p "$CLOUDCTL_STATE"
cp "$FIXTURES/account.json" "$CLOUDCTL_STATE/state.json"

failures=0
check() {  # check DESCRIPTION COMMAND...
    local desc="$1"; shift
    if "$@"; then echo "ok   - $desc"; else echo "FAIL - $desc"; failures=$((failures + 1)); fi
}
ids_for() {  # ids_for SELECTOR
    cloudctl list --selector "$1" --json | jq -r '.[].id' | sort
}

before_101="$(ids_for project=checkout,env=pr-101)"
before_102="$(ids_for project=checkout,env=pr-102)"

(cd "$APP_ROOT" && ./teardown.sh pr-101) > "$WORK/run1.out" 2>&1
rc1=$?
sed 's/^/    run1| /' "$WORK/run1.out"
check "first run exits 0" test "$rc1" -eq 0
check "every pr-101 resource is gone" test -z "$(ids_for project=checkout,env=pr-101)"
check "pr-102 is untouched" test "$(ids_for project=checkout,env=pr-102)" = "$before_102"

report="$REPORT_DIR/pr-101.md"
check "report written to reports/pr-101.md" test -s "$report"
for id in $before_101; do
    check "report lists $id" grep -qs -- "$id" "$report"
done

log_lines="$(wc -l < "$CLOUDCTL_STATE/calls.log")"
(cd "$APP_ROOT" && ./teardown.sh pr-101) > "$WORK/run2.out" 2>&1
rc2=$?
sed 's/^/    run2| /' "$WORK/run2.out"
check "second run exits 0" test "$rc2" -eq 0
check "second run says there is nothing to do" grep -qi "nothing to do" "$WORK/run2.out"
changes="$(tail -n +"$((log_lines + 1))" "$CLOUDCTL_STATE/calls.log" | jq -c 'select(.effects | length > 0)')"
check "second run changed nothing" test -z "$changes"

echo
if [[ "$failures" -eq 0 ]]; then echo "all checks passed"; else echo "$failures check(s) failed"; exit 1; fi
