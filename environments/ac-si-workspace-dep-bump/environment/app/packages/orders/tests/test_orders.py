import tempfile
import unittest
from decimal import Decimal

import fastjson
from orders.codec import OrderError, dump_receipt, parse_order
from orders.service import price_order, receipt_for, reload_total, store_receipts, summarize_batch

ORDER = ('{"order_id": "o-100", "currency": "eur", "discount": 1.10, "lines": ['
         '{"sku": "A", "qty": 3, "unit_price": 0.10, "tax_rate": 0.20},'
         '{"sku": "B", "qty": 1, "unit_price": 19.99, "tax_rate": 0.07}]}')


class CodecTest(unittest.TestCase):
    def test_amounts_are_exact(self):
        order = parse_order(ORDER)
        self.assertEqual(order["lines"][0]["unit_price"], Decimal("0.10"))
        self.assertIsInstance(order["discount"], Decimal)
        self.assertEqual(order["currency"], "EUR")

    def test_malformed_raises_order_error(self):
        with self.assertRaises(OrderError):
            parse_order('{"order_id": "o-1", "currency": "EUR", "lines": [')
        with self.assertRaises(OrderError):
            parse_order('{"order_id": "o-1"}')

    def test_receipt_is_canonical(self):
        receipt = {"total": Decimal("21.69"), "order_id": "o-100"}
        self.assertEqual(dump_receipt(receipt), '{"order_id": "o-100", "total": "21.69"}')


class ServiceTest(unittest.TestCase):
    def test_price_order(self):
        priced = price_order(parse_order(ORDER))
        self.assertEqual(priced["subtotal"], Decimal("20.29"))
        self.assertEqual(priced["tax"], Decimal("1.46"))
        self.assertEqual(priced["total"], Decimal("20.65"))

    def test_receipt_round_trip(self):
        text = receipt_for(ORDER)
        self.assertIn('"total": "20.65"', text)
        with tempfile.TemporaryDirectory() as d:
            ids = store_receipts(ORDER + "\nnot json\n", d)
            self.assertEqual(ids, ["o-100"])
            self.assertEqual(reload_total(f"{d}/o-100.json"), Decimal("20.65"))

    def test_batch_summary(self):
        batch = ORDER + "\n" + ORDER.replace("o-100", "o-101") + "\n{broken\n"
        summary = summarize_batch(batch)
        self.assertEqual(summary["orders"], 2)
        self.assertEqual(summary["totals"], {"EUR": Decimal("41.30")})
        self.assertEqual(len(summary["rejected"]), 1)

    def test_runs_on_fastjson_2(self):
        """SEC-118: orders must run on fastjson 2.x."""
        self.assertTrue(fastjson.VERSION.startswith("2."), f"running on fastjson {fastjson.VERSION}")


if __name__ == "__main__":
    unittest.main()
