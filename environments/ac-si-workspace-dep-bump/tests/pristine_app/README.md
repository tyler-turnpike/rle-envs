# Workspace

Two services share this workspace and its vendored dependencies:

| member | what | owners |
|---|---|---|
| `packages/orders` | order pricing and receipts | @payments-team |
| `packages/reports` | daily revenue ledger for finance close | @analytics-team |

The workspace ships **one version of each dependency** (`./mono check` resolves every member
together and writes `mono.lock`). Third-party code is vendored under `vendor/<name>-<version>/`;
there is no network access.

    ./mono check                 resolve + lock
    ./mono test orders           run a member's tests against the lock
    ./mono test orders --dep fastjson=2.1.0   try a member against another vendored version
    ./mono deps                  constraints and lock
    ./mono owners packages/reports

Workspace maintainers move a shared dependency for every package at once with
`./mono bump DEP VERSION --all`; on a major upgrade it runs the dependency's codemod over each
package. Owners are in `CODEOWNERS`.
