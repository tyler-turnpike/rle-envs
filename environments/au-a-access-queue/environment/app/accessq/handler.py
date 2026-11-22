"""Queue processing: parse -> validate -> decide -> apply -> file.

queue/new/   messages waiting to be handled
queue/cur/   messages whose changes were applied
queue/held/  messages left for the platform lead (sender not delegated, or invalid)
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .acl import AclStore
from .mailparse import ParseError, Request, parse_message
from .policy import Catalog, Delegation, min_holders


@dataclass
class Outcome:
    name: str
    ticket: str
    status: str  # applied | held | rejected
    detail: str


def _dirs(root: Path) -> tuple[Path, Path, Path]:
    q = root / "queue"
    return q / "new", q / "cur", q / "held"


def _move(path: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(dest / path.name))


def decide(req: Request, catalog: Catalog, delegation: Delegation) -> tuple[str, str]:
    unknown = [r for r in req.roles if not catalog.known(r)]
    if unknown:
        return "rejected", "unknown role(s): " + ", ".join(unknown)
    if not delegation.approves(req.sender):
        return "held", f"sender {req.sender} is not delegated"
    return "applied", ""


def check_min_holders(req: Request, store: AclStore, minimums: dict[str, int]) -> tuple[str, str]:
    """A revoke may not leave a role with fewer holders than its min_holders."""
    for role in req.roles:
        need = minimums.get(role, 0)
        if need and role in store.roles_of(req.principal):
            holders = sum(1 for roles in store.data["principals"].values() if role in roles)
            if holders - 1 < need:
                return "held", (f"revoking {role} from {req.principal} would leave {holders - 1} holder(s); "
                                f"policy requires min_holders = {need}")
    return "applied", ""


def apply(req: Request, store: AclStore, catalog: Catalog) -> list[str]:
    actor = req.sender
    changed = []
    if req.action == "grant":
        for role in catalog.expand(req.roles):
            if store.grant(req.principal, role, actor=actor, ticket=req.ticket,
                           msg_id=req.msg_id):
                changed.append("+" + role)
    else:
        for role in req.roles:
            if store.revoke(req.principal, role, actor=actor, ticket=req.ticket,
                            msg_id=req.msg_id):
                changed.append("-" + role)
    return changed


def process_queue(root: Path, dry_run: bool = False) -> list[Outcome]:
    root = Path(root)
    new, cur, held = _dirs(root)
    catalog = Catalog.load(root / "policy" / "roles.toml")
    minimums = min_holders(root / "policy" / "roles.toml")
    delegation = Delegation.load(root / "policy" / "delegation.toml")
    store = AclStore(root).load()
    outcomes: list[Outcome] = []

    for path in sorted(new.glob("*.eml")):
        try:
            req = parse_message(path)
        except ParseError as exc:
            outcomes.append(Outcome(path.name, "?", "rejected", str(exc)))
            _move(path, held)
            continue

        status, detail = decide(req, catalog, delegation)
        if status == "applied" and req.action == "revoke":
            status, detail = check_min_holders(req, store, minimums)
        if status == "applied":
            changed = apply(req, store, catalog)
            detail = " ".join(changed) or "no change"
            _move(path, cur)
        else:
            _move(path, held)
        outcomes.append(Outcome(path.name, req.ticket, status,
                                f"{req.action} {req.principal}: {detail}"))

    store.save()
    return outcomes
