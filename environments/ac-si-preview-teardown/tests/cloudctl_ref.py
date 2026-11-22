#!/usr/bin/env python3
"""cloudctl - command line client for the preview cloud account.

Installed as /usr/local/bin/cloudctl. Account data lives in $CLOUDCTL_STATE
(default /var/tmp/mockcloud); every invocation is appended to calls.log there.
"""
import copy
import fnmatch
import json
import os
import sys
import time

STATE_DIR = os.environ.get("CLOUDCTL_STATE", "/var/tmp/mockcloud")
KINDS = ("network", "subnet", "instance", "volume", "lb", "dns")

USAGE = """cloudctl - preview account CLI

usage:
  cloudctl list [--kind KIND] [--selector K=V[,K=V...]] [--match GLOB] [--json]
  cloudctl describe ID|NAME [--json]
  cloudctl deps ID|NAME [--json]       what depends on a resource
  cloudctl delete ID|NAME... [--force] [--dry-run]
  cloudctl delete (--selector K=V[,...] | --match GLOB) [--kind KIND] [--force] [--dry-run]
  cloudctl volume detach VOLUME
  cloudctl lb deregister LB INSTANCE
  cloudctl instance move INSTANCE --subnet SUBNET

kinds: network, subnet, instance, volume, lb, dns
labels: every resource carries project, env and owner labels; preview envs also
        carry an expires=YYYY-MM-DD label

delete:
  A resource that still has dependents is refused with DependencyViolation (exit 4):
  networks with subnets; subnets with instances or load balancers; instances with
  attached volumes, load-balancer registrations or DNS records; load balancers with
  DNS records; volumes that are still attached.
  --force      cascade: detach attached volumes, deregister from load balancers and
               delete every dependent resource first, then delete the target
  --selector   bulk delete of every resource whose labels match
  --match      bulk delete of every resource whose name matches GLOB (e.g. 'pr-*')
  --kind       restrict a bulk delete to one kind
  --dry-run    print what would happen, change nothing

instance move:
  stops the instance, re-homes it into SUBNET (attached volumes, load-balancer
  registrations and DNS records stay with it) and starts it again

exit codes: 0 ok, 2 usage, 3 not found, 4 dependency violation
account data: $CLOUDCTL_STATE (default /var/tmp/mockcloud)
"""


class CloudError(Exception):
    def __init__(self, code, msg, printed=False):
        super().__init__(msg)
        self.code = code
        self.printed = printed


def state_path():
    return os.path.join(STATE_DIR, "state.json")


def load_state():
    with open(state_path()) as f:
        return json.load(f)


def save_state(state):
    tmp = state_path() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    os.replace(tmp, state_path())


def log_call(argv, code, effects, error, dry_run):
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "argv": argv, "exit": code,
             "dry_run": dry_run, "effects": effects, "error": error}
    try:
        with open(os.path.join(STATE_DIR, "calls.log"), "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def resolve(state, ref):
    res = state["resources"]
    if ref in res:
        return res[ref]
    named = [r for r in res.values() if r["name"] == ref]
    if not named:
        raise CloudError(3, "NotFound: no resource %r" % ref)
    return named[0]


def dependents(state, rid):
    out = []
    for o in sorted(state["resources"].values(), key=lambda r: r["id"]):
        k = o["kind"]
        if (k == "subnet" and o.get("network") == rid) \
                or (k in ("instance", "lb") and o.get("subnet") == rid) \
                or (k == "volume" and o.get("attached_to") == rid) \
                or (k == "lb" and rid in o.get("targets", [])) \
                or (k == "dns" and o.get("target") == rid):
            out.append(o)
    return out


def brief(r):
    return "%s %s (%s)" % (r["kind"], r["id"], r["name"])


def effect(effects, r, action, detail=""):
    effects.append({"id": r["id"], "kind": r["kind"], "name": r["name"],
                    "labels": r.get("labels", {}), "action": action, "detail": detail})


def detach(state, vol, effects):
    if not vol.get("attached_to"):
        raise CloudError(2, "volume %s is not attached" % vol["id"])
    old = vol["attached_to"]
    vol["attached_to"] = None
    vol["status"] = "available"
    effect(effects, vol, "detached", "from " + old)


def delete(state, r, force, effects):
    res = state["resources"]
    if r["kind"] == "volume" and r.get("attached_to"):
        if not force:
            raise CloudError(4, "DependencyViolation: %s is attached to instance %s; detach it first"
                             % (brief(r), r["attached_to"]))
        detach(state, r, effects)
    deps = dependents(state, r["id"])
    if deps and not force:
        raise CloudError(4, "DependencyViolation: %s has dependent resources: %s"
                         % (brief(r), ", ".join(brief(d) for d in deps)))
    for d in deps:
        if d["id"] not in res:
            continue
        if d["kind"] == "volume":
            detach(state, d, effects)
        elif d["kind"] == "lb" and r["id"] in d.get("targets", []):
            d["targets"].remove(r["id"])
            effect(effects, d, "deregistered", r["id"])
        else:
            delete(state, d, True, effects)
    del res[r["id"]]
    effect(effects, r, "deleted")


def parse_selector(text):
    sel = {}
    for part in text.split(","):
        if "=" not in part:
            raise CloudError(2, "bad selector %r (want k=v[,k=v])" % text)
        k, v = part.split("=", 1)
        sel[k.strip()] = v.strip()
    return sel


def select(state, kind=None, selector=None, match=None):
    out = []
    for r in sorted(state["resources"].values(), key=lambda r: r["id"]):
        if kind and r["kind"] != kind:
            continue
        if selector and any(r["labels"].get(k) != v for k, v in selector.items()):
            continue
        if match and not fnmatch.fnmatch(r["name"], match):
            continue
        out.append(r)
    return out


def show(state, r):
    lines = ["%-12s %s" % (k + ":", r[k]) for k in ("id", "kind", "name", "status") if k in r]
    lines.append("%-12s %s" % ("labels:", ",".join("%s=%s" % kv for kv in sorted(r["labels"].items()))))
    for k in ("network", "subnet", "attached_to", "targets", "target", "size_gb", "created"):
        if k in r:
            lines.append("%-12s %s" % (k + ":", r[k]))
    deps = dependents(state, r["id"])
    lines.append("dependents:  " + (", ".join(brief(d) for d in deps) if deps else "none"))
    return "\n".join(lines)


def take(args, flag, has_value=True):
    if flag not in args:
        return None
    i = args.index(flag)
    if not has_value:
        args.pop(i)
        return True
    if i + 1 >= len(args):
        raise CloudError(2, "%s needs a value" % flag)
    args.pop(i)
    return args.pop(i)


def run(argv, effects):
    args = list(argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0, False
    cmd = args.pop(0)
    as_json = bool(take(args, "--json", False))
    force = bool(take(args, "--force", False))
    dry = bool(take(args, "--dry-run", False))
    kind = take(args, "--kind")
    sel = take(args, "--selector")
    match = take(args, "--match")
    to_subnet = take(args, "--subnet")
    if kind and kind not in KINDS:
        raise CloudError(2, "unknown kind %r" % kind)
    state = load_state()
    if cmd == "list":
        rows = select(state, kind, parse_selector(sel) if sel else None, match)
        if as_json:
            print(json.dumps(rows, indent=2))
        else:
            for r in rows:
                lb = r["labels"]
                print("%-14s %-9s %-36s %-10s %-8s %s" % (r["id"], r["kind"], r["name"], lb.get("project", "-"),
                                                       lb.get("env", "-"), r.get("status", "-")))
        return 0, False
    if cmd in ("describe", "deps"):
        if len(args) != 1:
            raise CloudError(2, "usage: cloudctl %s ID|NAME" % cmd)
        r = resolve(state, args[0])
        if cmd == "deps":
            deps = dependents(state, r["id"])
            print(json.dumps(deps, indent=2) if as_json else "\n".join(brief(d) for d in deps) or "none")
        else:
            print(json.dumps(dict(r, dependents=[d["id"] for d in dependents(state, r["id"])]), indent=2)
                  if as_json else show(state, r))
        return 0, False
    work = copy.deepcopy(state) if dry else state
    if cmd == "delete":
        if sel or match:
            targets = select(work, kind, parse_selector(sel) if sel else None, match)
        elif args:
            targets = [resolve(work, a) for a in args]
        else:
            raise CloudError(2, "usage: cloudctl delete ID|NAME... | --selector K=V | --match GLOB")
        errors = []
        for t in targets:
            if t["id"] not in work["resources"]:
                continue
            try:
                delete(work, t, force, effects)
                print("%sdeleted %s" % ("(dry-run) would have " if dry else "", brief(t)))
            except CloudError as e:
                errors.append(e)
                print("error: %s" % e, file=sys.stderr)
        if not dry:
            save_state(work)
        if errors:
            raise CloudError(max(e.code for e in errors), "; ".join(str(e) for e in errors), True)
        return 0, dry
    if cmd == "volume" and args[:1] == ["detach"] and len(args) == 2:
        detach(work, resolve(work, args[1]), effects)
    elif cmd == "instance" and args[:1] == ["move"] and len(args) == 2 and to_subnet:
        inst, sub = resolve(work, args[1]), resolve(work, to_subnet)
        if inst["kind"] != "instance" or sub["kind"] != "subnet":
            raise CloudError(2, "usage: cloudctl instance move INSTANCE --subnet SUBNET")
        if inst["subnet"] != sub["id"]:
            old, inst["subnet"] = inst["subnet"], sub["id"]
            inst["restarted"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            effect(effects, inst, "moved", "%s -> %s" % (old, sub["id"]))
    elif cmd == "lb" and args[:1] == ["deregister"] and len(args) == 3:
        lb, inst = resolve(work, args[1]), resolve(work, args[2])
        if inst["id"] not in lb.get("targets", []):
            raise CloudError(2, "%s is not registered with %s" % (inst["id"], lb["id"]))
        lb["targets"].remove(inst["id"])
        effect(effects, lb, "deregistered", inst["id"])
    else:
        raise CloudError(2, "unknown command; see cloudctl --help")
    if not dry:
        save_state(work)
    for e in effects:
        print("%s %s %s" % (e["action"], e["kind"], e["id"]))
    return 0, dry


def main():
    argv = sys.argv[1:]
    effects = []
    try:
        code, dry = run(argv, effects)
        log_call(argv, code, [] if dry else effects, None, dry)
        return code
    except CloudError as e:
        if not e.printed:
            print("error: %s" % e, file=sys.stderr)
        log_call(argv, e.code, [] if "--dry-run" in argv else effects, str(e), "--dry-run" in argv)
        return e.code
    except (OSError, ValueError) as e:
        print("error: cannot read account data in %s: %s" % (STATE_DIR, e), file=sys.stderr)
        log_call(argv, 1, [], str(e), False)
        return 1


if __name__ == "__main__":
    sys.exit(main())
