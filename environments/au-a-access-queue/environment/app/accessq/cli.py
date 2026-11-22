"""Command line entry point: python -m accessq.cli [--root DIR] <command>."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .acl import AclStore
from .handler import process_queue

DEFAULT_ROOT = Path(__file__).resolve().parent.parent


def cmd_process(args) -> int:
    outcomes = process_queue(args.root, dry_run=args.dry_run)
    if not outcomes:
        print("queue/new is empty")
    for o in outcomes:
        print(f"{o.status:9} {o.ticket:8} {o.name}  {o.detail}")
    if args.dry_run:
        print("(dry run: nothing written)")
    return 0


def cmd_show(args) -> int:
    store = AclStore(args.root).load()
    principals = [args.principal] if args.principal else sorted(store.data["principals"])
    for p in principals:
        print(f"{p}: {', '.join(store.roles_of(p)) or '-'}")
    return 0


def cmd_grant(args) -> int:
    """Direct grant outside the queue (platform lead / on-call admin, e.g. during an incident)."""
    store = AclStore(args.root).load()
    if store.grant(args.principal, args.role, actor="accessq-cli", ticket=args.ticket, msg_id=""):
        store.save()
        print(f"granted {args.role} to {args.principal} ({args.ticket})")
    else:
        print(f"{args.principal} already has {args.role}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="accessq")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                        help="repository root holding queue/, state/ and policy/")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("process", help="handle everything in queue/new")
    p.add_argument("--dry-run", action="store_true",
                   help="report what would happen without writing anything")
    p.set_defaults(func=cmd_process)

    s = sub.add_parser("show", help="print current role assignments")
    s.add_argument("principal", nargs="?")
    s.set_defaults(func=cmd_show)

    g = sub.add_parser("grant", help="admin: grant a role directly, outside the queue (audited)")
    g.add_argument("principal")
    g.add_argument("role")
    g.add_argument("--ticket", required=True, help="ticket or incident reference for the audit log")
    g.set_defaults(func=cmd_grant)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
