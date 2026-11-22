"""Role catalog (policy/roles.toml) and delegation settings (policy/delegation.toml)."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class Role:
    name: str
    description: str
    implies: tuple[str, ...] = ()


class Catalog:
    def __init__(self, roles: dict[str, Role]):
        self.roles = roles
        for role in roles.values():
            for dep in role.implies:
                if dep not in roles:
                    raise PolicyError(f"{role.name} implies unknown role {dep}")

    @classmethod
    def load(cls, path: Path) -> "Catalog":
        with open(path, "rb") as fh:
            raw = tomllib.load(fh)
        roles = {}
        for name, spec in raw.get("roles", {}).items():
            roles[name] = Role(name, spec.get("description", ""),
                               tuple(spec.get("implies", ())))
        return cls(roles)

    def known(self, name: str) -> bool:
        return name in self.roles

    def expand(self, names: list[str]) -> list[str]:
        """The roles to grant for a request: each named role plus what it implies."""
        out: list[str] = []
        for name in names:
            out.append(name)
            out.extend(self.roles[name].implies)
        return out


@dataclass
class Delegation:
    approved_senders: list[str]

    @classmethod
    def load(cls, path: Path) -> "Delegation":
        if not path.exists():
            return cls([])
        with open(path, "rb") as fh:
            raw = tomllib.load(fh)
        return cls(list(raw.get("approved_senders", [])))

    def approves(self, sender: str) -> bool:
        return sender in self.approved_senders
