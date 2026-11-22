# shellcheck shell=bash
# Teardown report: one markdown file per env under $REPORT_DIR.
#
#   report_init ENV           start a new report (truncates the scratch rows)
#   report_add ACTION ID KIND NAME [NOTE]
#   report_write              render reports/<env>.md, prints its path

REPORT_DIR="${REPORT_DIR:-$ROOT/reports}"
_REPORT_ENV=""
_REPORT_ROWS=""

report_init() {
    _REPORT_ENV="$1"
    mkdir -p "$REPORT_DIR"
    _REPORT_ROWS="$(mktemp)"
}

report_add() {
    [[ -n "$_REPORT_ROWS" ]] || { echo "report: report_init not called" >&2; return 1; }
    local action="$1" id="$2" kind="$3" name="$4" note="${5:-}"
    printf '%s\t%s\t%s\t%s\t%s\n' "$action" "$id" "$kind" "$name" "$note" >> "$_REPORT_ROWS"
}

report_path() {
    echo "$REPORT_DIR/${_REPORT_ENV}.md"
}

report_write() {
    local out action id kind name note
    out="$(report_path)"
    {
        echo "# Teardown report: ${_REPORT_ENV}"
        echo
        echo "- generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "- selector: ${ENV_SELECTOR:-?}"
        echo
        if [[ ! -s "$_REPORT_ROWS" ]]; then
            echo "Nothing to do: no resources matched."
        else
            echo "| action | id | kind | name | note |"
            echo "|---|---|---|---|---|"
            while IFS=$'\t' read -r action id kind name note; do
                echo "| $action | $id | $kind | $name | $note |"
            done < "$_REPORT_ROWS"
        fi
    } > "$out"
    rm -f "$_REPORT_ROWS"
    echo "$out"
}
