import unittest
from decimal import Decimal

from reports.ledger import average_ticket, daily_ledger, ledger_json

EXPORT = "\n".join([
    '{"day": "2026-11-20", "order_id": "o-1", "total": 0.10, "tax": 0.02}',
    '{"day": "2026-11-20", "order_id": "o-2", "total": 0.20, "tax": 0.01}',
    '{"day": "2026-11-21", "order_id": "o-3", "total": 1999.99, "tax": 130.84}',
])


class LedgerTest(unittest.TestCase):
    def test_daily_totals_are_exact(self):
        ledger = daily_ledger(EXPORT)
        self.assertEqual(ledger["2026-11-20"]["revenue"], Decimal("0.30"))
        self.assertEqual(ledger["2026-11-20"]["tax"], Decimal("0.03"))
        self.assertEqual(ledger["2026-11-21"]["orders"], 1)

    def test_average_ticket(self):
        self.assertEqual(average_ticket(EXPORT), Decimal("666.76"))

    def test_ledger_json_keeps_cents(self):
        self.assertIn('"revenue": "0.30"', ledger_json(EXPORT))


if __name__ == "__main__":
    unittest.main()
