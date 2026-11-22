"""ACL state (state/acl.json) and the append-only audit log (state/audit.log)."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


class AclStore:
    def __init__(self, root: Path):
        self.acl_path = Path(root) / "state" / "acl.json"
        self.audit_path = Path(root) / "state" / "audit.log"
        self.data: dict = {}

    def load(self) -> "AclStore":
        with open(self.acl_path) as fh:
            self.data = json.load(fh)
        self.data.setdefault("principals", {})
        return self

    def roles_of(self, principal: str) -> list[str]:
        return list(self.data["principals"].get(principal, []))

    def grant(self, principal: str, role: str, *, actor: str, ticket: str,
              msg_id: str) -> bool:
        roles = self.data["principals"].setdefault(principal, [])
        roles.append(role)
        roles.sort()
        self.audit(action="grant", principal=principal, role=role, actor=actor,
                   ticket=ticket, msg_id=msg_id, result="applied")
        return True

    def revoke(self, principal: str, role: str, *, actor: str, ticket: str,
               msg_id: str) -> bool:
        raise NotImplementedError("revocations are not supported yet")

    def save(self) -> None:
        self.data["updated"] = _now()
        fd, tmp = tempfile.mkstemp(dir=self.acl_path.parent, prefix=".acl-")
        with os.fdopen(fd, "w") as fh:
            json.dump(self.data, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, self.acl_path)

    def audit(self, **entry) -> None:
        """Append one JSON line. Never rewrite or truncate the log."""
        line = json.dumps({"ts": _now(), **entry}, sort_keys=True)
        with open(self.audit_path, "a") as fh:
            fh.write(line + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
