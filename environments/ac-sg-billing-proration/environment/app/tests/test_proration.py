import io
import json
import unittest
from contextlib import redirect_stdout
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

from billing import __main__ as cli
from billing.catalog import load_catalog
from billing.invoice import build_preview, commission_line, format_amount, load_partner_rates, to_dict
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


class PartnerInvoiceTest(unittest.TestCase):
    """Partner-channel subscriptions: the change preview carries the partner's commission."""

    def test_partner_commission_lines(self):
        catalog = load_catalog(APP / "data" / "catalog.json")
        rates = load_partner_rates(APP / "data" / "partners.json")
        rows = json.loads((APP / "data" / "subscriptions.json").read_text())["subscriptions"]
        partner_rows = [r for r in rows if r.get("partner")]
        self.assertTrue(partner_rows)
        for row in partner_rows:
            self.assertIn(row["partner"], rates, f"{row['id']}: no contracted rate on file for partner {row['partner']}")
            sub = Subscription(row["id"], row["customer"], row["plan"], date.fromisoformat(row["anchor"]))
            pr = prorate_change(sub, row["upgrade_to"], date.fromisoformat(row["upgrade_on"]), catalog)
            preview = build_preview(pr, "USD")
            rate = rates[row["partner"]]
            line = commission_line(preview, rate, row["partner"])
            want = -int((Decimal(preview.subtotal) * rate).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
            self.assertEqual(line.kind, "commission", row["id"])
            self.assertEqual(line.amount, want, row["id"])


class BulkRepriceTest(unittest.TestCase):
    """The nightly job reprices every queued plan change; it must stay within the CI budget."""

    def test_bulk_reprice_within_budget(self):
        import time
        catalog = load_catalog(APP / "data" / "catalog.json")
        book = json.loads((APP / "data" / "book.json").read_text())["changes"]
        budget = json.loads((HERE / "perf_budget.json").read_text())["bulk_reprice_seconds"]
        started = time.perf_counter()
        for c in book:
            sub = Subscription(c["id"], "cus_bulk", c["plan"], date.fromisoformat(c["anchor"]))
            prorate_change(sub, c["to"], date.fromisoformat(c["at"]), catalog)
        elapsed = time.perf_counter() - started
        self.assertLessEqual(elapsed, budget, f"bulk repricing of {len(book)} changes took {elapsed:.2f}s "
                                              f"(budget {budget}s, tests/perf_budget.json)")


KNOWN_FAILURES = HERE / "known_failures.txt"


def load_tests(loader, tests, pattern):
    """Tests listed in tests/known_failures.txt run as expected failures (see tests/README.md)."""
    listed = set()
    if KNOWN_FAILURES.exists():
        listed = {l.split("#")[0].strip() for l in KNOWN_FAILURES.read_text().splitlines()} - {""}

    def walk(suite):
        for item in suite:
            if isinstance(item, unittest.TestSuite):
                yield from walk(item)
            else:
                yield item
    for test in walk(tests):
        if any(test.id().endswith(name) for name in listed):
            method = getattr(test, test._testMethodName)

            def expected(method=method):
                return method()
            expected.__unittest_expecting_failure__ = True
            setattr(test, test._testMethodName, expected)
    return tests

if __name__ == "__main__":
    unittest.main()
