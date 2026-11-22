import io
import json
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

from billing import __main__ as cli
from billing.catalog import load_catalog
from billing.invoice import build_preview, format_amount, to_dict
from billing.proration import Subscription, portion, prorate_change

HERE = Path(__file__).resolve().parent
APP = HERE.parent
CASES = json.loads((HERE / "fixtures" / "plan_changes.json").read_text())["cases"]


class WorkedExamplesTest(unittest.TestCase):
    """Finance's worked examples (docs/proration.md, rev. 4)."""

    def setUp(self):
        self.catalog = load_catalog(APP / "data" / "catalog.json")

    def test_worked_examples(self):
        for case in CASES:
            with self.subTest(case=case["id"]):
                sub = Subscription("sub_x", "cus_x", case["plan"], date.fromisoformat(case["anchor"]))
                got = prorate_change(sub, case["to"], date.fromisoformat(case["at"]), self.catalog)
                exp = case["expected"]
                self.assertEqual((got.period_start.isoformat(), got.period_end.isoformat()),
                                 (exp["period_start"], exp["period_end"]))
                self.assertEqual(got.credit, exp["credit"])
                self.assertEqual(got.charge, exp["charge"])
                self.assertEqual(got.total, exp["total"])
                self.assertEqual(got.new_anchor.isoformat(), exp["new_anchor"])
                self.assertEqual(got.next_renewal.isoformat(), exp["next_renewal"])


class PortionTest(unittest.TestCase):
    def test_half_even(self):
        self.assertEqual(portion(1, 1, 2), 0)
        self.assertEqual(portion(3, 1, 2), 2)
        self.assertEqual(portion(4900, 15, 28), 2625)

    def test_rejects_bad_fraction(self):
        with self.assertRaises(ValueError):
            portion(100, 5, 4)


class InvoiceTest(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog(APP / "data" / "catalog.json")

    def test_downgrade_carries_credit(self):
        sub = Subscription("sub_9", "cus_9", "team-monthly", date(2025, 3, 14))
        pr = prorate_change(sub, "starter-monthly", date(2026, 6, 20), self.catalog)
        preview = build_preview(pr, "USD")
        self.assertEqual(preview.amount_due, 0)
        self.assertEqual(preview.credit_carried, pr.credit - pr.charge)
        self.assertEqual([l["kind"] for l in to_dict(preview)["lines"]], ["credit", "charge"])

    def test_format_amount(self):
        self.assertEqual(format_amount(123456, "USD"), "1,234.56 USD")
        self.assertEqual(format_amount(-5, "USD"), "-0.05 USD")
        self.assertEqual(format_amount(500, "JPY"), "500 JPY")

    def test_cli_json_preview(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.main(["preview", "--sub", str(APP / "data" / "subscriptions.json"),
                      "--id", "sub_1001", "--to", "pro-monthly", "--at", "2026-06-20",
                      "--catalog", str(APP / "data" / "catalog.json"), "--json"])
        doc = json.loads(buf.getvalue())
        self.assertEqual(doc["subscription"], "sub_1001")
        self.assertEqual(doc["subtotal"], 2960)
        self.assertEqual(doc["amount_due"], 2960)


if __name__ == "__main__":
    unittest.main()
