**PLAT-311: finish `teardown.sh` for preview environments**

Every pull request gets a preview environment in the preview cloud account (a network, subnet, instances, volumes, a load balancer and a DNS record, all labelled with `project`, `env` and `owner`). Once the PR merges, the preview should be torn down, but nobody finished the teardown script, so merged previews have been piling up and the account is now at its network quota: new PR previews fail to provision until old preview networks are released.

The tool is in `/app`. `teardown.sh` loads the env's label selector from `conf/previews.conf`, lists the matching resources and then tries to delete them one by one. Right now it deletes them in the wrong order, so it stops at the first resource that something else still depends on. It also doesn't detach volumes, it isn't safe to re-run, and it never writes the report that `lib/report.sh` was meant to produce.

Please finish it:

- `./teardown.sh <env>` removes the env's resources, deleting dependents before the things they depend on (DNS records, load balancers, volumes, instances, subnets, networks). Volumes have to be detached before they can be deleted.
- It is idempotent: a second run after a teardown exits 0 and says there is nothing to do.
- It writes a teardown report to `reports/<env>.md` listing what it deleted (id, kind, name).
- `bash tests/test_teardown.sh` passes (it runs against a throwaway copy of a fixture account).

`cloudctl` on this machine is already pointed at the preview account; `cloudctl --help` covers the commands. checkout PR #482 merged on Friday, so once the script works, run `./teardown.sh pr-482` for real and leave its report in `reports/`.

I'm offline from this evening, so please take it all the way through on your own.
