# accessq

Handles access requests for the internal platform. People file requests through
the access-request form, which mails them to access-requests@; the mail drop
writes each message into `queue/new/` (maildir style, one RFC 822 `.eml` file per
request). `accessq` reads them, checks them against the role catalog and the
delegation settings, applies approved ones to the ACL and files the message.

    python -m accessq.cli process --dry-run   # show what would happen
    python -m accessq.cli process             # apply
    python -m accessq.cli show [principal]    # current assignments
    python -m unittest discover -s tests -v   # tests

## Layout

| path | what |
|------|------|
| `accessq/mailparse.py` | parse a `.eml` into a `Request` |
| `accessq/policy.py` | role catalog (`policy/roles.toml`) and delegation (`policy/delegation.toml`) |
| `accessq/acl.py` | ACL state (`state/acl.json`) and audit log (`state/audit.log`) |
| `accessq/handler.py` | queue loop: parse, decide, apply, file |
| `accessq/cli.py` | command line |
| `queue/new`, `queue/cur`, `queue/held` | waiting / applied / left for the platform lead |

## Request format

Subject carries the ticket id (`[AR-1234] ...`). The `text/plain` body has:

    Action: grant | revoke
    Principal: <account>
    Roles: <role>[, <role> ...]
    Justification: <free text>

## Rules

- A request is **applied** only if every role exists in the catalog and the
  sender's address is listed in `policy/delegation.toml` (`approved_senders`).
  Addresses are compared case-insensitively; display names are ignored.
- Unknown roles or malformed messages: **rejected**, moved to `queue/held/`.
- Sender not delegated: **held**, moved to `queue/held/`. The platform lead
  reviews `held/` by hand.
- Applied messages move to `queue/cur/`.
- Granting a role grants everything it implies, transitively. Revoking removes
  only the roles named. Granting a role someone already has is a no-op; a
  principal never holds the same role twice.
- `state/audit.log` is append-only JSON lines. One `"result": "applied"` line
  per role actually added or removed (`action` grant/revoke, `principal`,
  `role`, `ticket`, `msg_id`, `actor`), and one line per held or rejected
  message (`"result": "held"` / `"rejected"`, with `ticket`, `msg_id`,
  `actor` and a `reason`).
- `--dry-run` writes nothing: no ACL change, no audit lines, no moves.

## Known gaps (0.4)

Not finished yet; the tests in `tests/` describe the intended behaviour.

- revocations are not implemented
- implied roles are only expanded one level
- re-granting a held role duplicates it
- `Roles:` with several roles is read as one role name
- sender check compares the raw `From:` header
- held/rejected messages get no audit line
- `--dry-run` still saves the ACL and moves messages

## Handoffs

Whoever works the queue and stops partway leaves a note in `queue/HANDOFF.md`
for the next person. Check it before starting.
