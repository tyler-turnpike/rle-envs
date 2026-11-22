"""Run with: python -m unittest discover -s tests -v   (from the repo root)."""
import json
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

from accessq.handler import process_queue

REPO = Path(__file__).resolve().parent.parent
LEAD = "lead@example.test"


def message(ticket, sender, action, principal, roles, msg_id=None):
    return textwrap.dedent(f"""\
        From: {sender}
        To: access-requests@example.test
        Subject: [{ticket}] access request
        Message-ID: <{msg_id or ticket}@example.test>
        Date: Mon, 16 Nov 2026 09:00:00 +0000
        Content-Type: text/plain; charset=utf-8

        Action: {action}
        Principal: {principal}
        Roles: {roles}
        Justification: test

        --
        sent from the access-request form
        """)


class QueueCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        (self.root / "policy").mkdir()
        shutil.copy(REPO / "policy" / "roles.toml", self.root / "policy" / "roles.toml")
        (self.root / "policy" / "delegation.toml").write_text(
            f'approved_senders = ["{LEAD}"]\n')
        (self.root / "state").mkdir()
        self.write_acl({"ana": ["ci-viewer"], "bo": ["billing-reader", "ci-viewer"], "zed": ["billing-reader"]})
        (self.root / "state" / "audit.log").write_text("")
        for d in ("new", "cur", "held"):
            (self.root / "queue" / d).mkdir(parents=True)

    def write_acl(self, principals):
        (self.root / "state" / "acl.json").write_text(
            json.dumps({"principals": principals}))

    def enqueue(self, name, text):
        (self.root / "queue" / "new" / f"{name}.eml").write_text(text)

    def acl(self):
        return json.loads((self.root / "state" / "acl.json").read_text())["principals"]

    def audit(self):
        text = (self.root / "state" / "audit.log").read_text()
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def listing(self, d):
        return sorted(p.name for p in (self.root / "queue" / d).iterdir())


class GrantTests(QueueCase):
    def test_grant_applies_and_files_message(self):
        self.enqueue("1", message("AR-1", f"Team Lead <{LEAD}>", "grant", "ana", "billing-reader"))
        process_queue(self.root)
        self.assertEqual(self.acl()["ana"], ["billing-reader", "ci-viewer"])
        self.assertEqual(self.listing("cur"), ["1.eml"])
        self.assertTrue(any(e.get("ticket") == "AR-1" and e.get("result") == "applied"
                            for e in self.audit()))

    def test_sender_match_ignores_case(self):
        self.enqueue("1", message("AR-2", "LEAD@Example.TEST", "grant", "ana", "billing-reader"))
        process_queue(self.root)
        self.assertIn("billing-reader", self.acl()["ana"])

    def test_implied_roles_are_granted_transitively(self):
        self.enqueue("1", message("AR-3", LEAD, "grant", "cy", "release-manager"))
        process_queue(self.root)
        self.assertEqual(self.acl()["cy"], ["artifact-publisher", "ci-viewer",
                                            "deploy-operator", "release-manager"])

    def test_grant_is_idempotent(self):
        self.enqueue("1", message("AR-4", LEAD, "grant", "ana", "deploy-operator"))
        self.enqueue("2", message("AR-5", LEAD, "grant", "ana", "ci-viewer"))
        process_queue(self.root)
        self.assertEqual(self.acl()["ana"], ["ci-viewer", "deploy-operator"])

    def test_several_roles_in_one_request(self):
        self.enqueue("1", message("AR-6", LEAD, "grant", "ana", "billing-reader, oncall-responder"))
        process_queue(self.root)
        self.assertEqual(self.acl()["ana"], ["billing-reader", "ci-viewer", "oncall-responder"])


class RevokeTests(QueueCase):
    def test_revoke_removes_only_named_roles(self):
        self.enqueue("1", message("AR-7", LEAD, "revoke", "bo", "billing-reader"))
        process_queue(self.root)
        self.assertEqual(self.acl()["bo"], ["ci-viewer"])
        self.assertTrue(any(e.get("action") == "revoke" and e.get("role") == "billing-reader"
                            for e in self.audit()))


class HoldTests(QueueCase):
    def test_unknown_role_is_rejected(self):
        self.enqueue("1", message("AR-8", LEAD, "grant", "ana", "root"))
        process_queue(self.root)
        self.assertEqual(self.acl()["ana"], ["ci-viewer"])
        self.assertEqual(self.listing("held"), ["1.eml"])

    def test_undelegated_sender_is_held_and_audited(self):
        self.enqueue("1", message("AR-9", "someone@example.test", "grant", "ana", "billing-reader"))
        process_queue(self.root)
        self.assertEqual(self.acl()["ana"], ["ci-viewer"])
        self.assertEqual(self.listing("held"), ["1.eml"])
        self.assertTrue(any(e.get("ticket") == "AR-9" and e.get("result") == "held"
                            for e in self.audit()))

    def test_dry_run_writes_nothing(self):
        self.enqueue("1", message("AR-10", LEAD, "grant", "ana", "billing-reader"))
        before = (self.root / "state" / "acl.json").read_text()
        process_queue(self.root, dry_run=True)
        self.assertEqual((self.root / "state" / "acl.json").read_text(), before)
        self.assertEqual(self.audit(), [])
        self.assertEqual(self.listing("new"), ["1.eml"])


if __name__ == "__main__":
    unittest.main()
