# shellcheck shell=bash
# Inventory helpers: map a preview env to its label selector and list what it owns.
#
# Environment overrides:
#   CLOUDCTL        cloudctl binary to call (default: cloudctl on PATH)
#   PREVIEWS_CONF   env -> selector mapping (default: conf/previews.conf)

CLOUDCTL="${CLOUDCTL:-cloudctl}"
PREVIEWS_CONF="${PREVIEWS_CONF:-$ROOT/conf/previews.conf}"

# load_env_config ENV
# Sets ENV_NAME, ENV_PROJECT and ENV_SELECTOR from the config file.
load_env_config() {
    local want="$1" env project selector
    [[ -r "$PREVIEWS_CONF" ]] || { echo "inventory: cannot read $PREVIEWS_CONF" >&2; return 1; }
    while read -r env project selector _; do
        [[ -z "$env" || "$env" == \#* ]] && continue
        if [[ "$env" == "$want" ]]; then
            ENV_NAME="$env"
            ENV_PROJECT="$project"
            ENV_SELECTOR="$selector"
            return 0
        fi
    done < "$PREVIEWS_CONF"
    echo "inventory: unknown preview env '$want' (see $PREVIEWS_CONF)" >&2
    return 1
}

# inventory_collect SELECTOR
# Prints one line per resource: "<id>\t<kind>\t<name>".
inventory_collect() {
    local selector="$1"
    "$CLOUDCTL" list --selector "$selector" --json \
        | jq -r '.[] | [.id, .kind, .name] | @tsv'
}

# inventory_json ID
# Full JSON description of one resource (includes "dependents": [ids]).
inventory_json() {
    "$CLOUDCTL" describe "$1" --json
}

# inventory_field ID FIELD
# Prints one top-level field of a resource ("" when unset).
inventory_field() {
    inventory_json "$1" | jq -r --arg f "$2" '.[$f] // empty'
}

# inventory_exists ID -> 0 if the resource is still there
inventory_exists() {
    "$CLOUDCTL" describe "$1" >/dev/null 2>&1
}
