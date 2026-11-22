"""Parse access-request messages (RFC 822 / .eml) from the queue.

A request body is a block of ``Key: value`` lines, for example::

    Action: grant
    Principal: priya.raman
    Roles: deploy-operator
    Justification: joining the deploy rotation

Anything after a ``-- `` signature separator is ignored.
"""
from __future__ import annotations

import email
import re
from dataclasses import dataclass
from email import policy as email_policy
from pathlib import Path

TICKET_RE = re.compile(r"\[(AR-\d+)\]")
FIELD_RE = re.compile(r"^([A-Za-z-]+)\s*:\s*(.*)$")
ACTIONS = ("grant", "revoke")


class ParseError(ValueError):
    """The message is not a well-formed access request."""


@dataclass
class Request:
    path: Path
    msg_id: str
    ticket: str
    sender: str
    action: str
    principal: str
    roles: list[str]
    justification: str = ""


def _plain_body(msg) -> str:
    part = msg.get_body(preferencelist=("plain",))
    if part is None:
        raise ParseError("no text/plain part")
    return part.get_content()


def parse_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if line.rstrip() == "--":
            break
        m = FIELD_RE.match(line.strip())
        if m:
            fields.setdefault(m.group(1).lower(), m.group(2).strip())
    return fields


def parse_message(path: Path) -> Request:
    with open(path, "rb") as fh:
        msg = email.message_from_binary_file(fh, policy=email_policy.default)
    subject = str(msg.get("Subject", ""))
    m = TICKET_RE.search(subject)
    if not m:
        raise ParseError(f"no ticket id in subject {subject!r}")
    fields = parse_fields(_plain_body(msg))
    action = fields.get("action", "").lower()
    if action not in ACTIONS:
        raise ParseError(f"unsupported action {action!r}")
    principal = fields.get("principal", "")
    if not principal:
        raise ParseError("missing Principal")
    if not fields.get("roles"):
        raise ParseError("missing Roles")
    # TODO: Roles may list several roles, comma separated
    roles = [fields["roles"].strip()]
    return Request(
        path=path,
        msg_id=str(msg.get("Message-ID", "")).strip(),
        ticket=m.group(1),
        sender=str(msg.get("From", "")),
        action=action,
        principal=principal,
        roles=roles,
        justification=fields.get("justification", ""),
    )
