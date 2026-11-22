# shellcheck shell=bash
# Ordering of resources for teardown.
#
# Resources have to go in reverse dependency order: cloudctl refuses to delete
# anything that still has dependents (see `cloudctl --help`).

# order_rank KIND -> numeric rank; lower ranks are processed first.
# NOTE: copied from the provisioning side (create order) -- still needs to be
# turned into a teardown order and to cover every kind we provision.
order_rank() {
    case "$1" in
        network)  echo 10 ;;
        subnet)   echo 20 ;;
        instance) echo 30 ;;
        *)        echo 99 ;;
    esac
}

# order_resources < "<id>\t<kind>\t<name>" lines
# Prints the same lines sorted by rank (stable within a rank).
order_resources() {
    local id kind name
    while IFS=$'\t' read -r id kind name; do
        [[ -z "$id" ]] && continue
        printf '%s\t%s\t%s\t%s\n' "$(order_rank "$kind")" "$id" "$kind" "$name"
    done | sort -s -n -k1,1 | cut -f2-
}
