import unittest
from datetime import date

from billing.calendar import add_months, cycle_bounds, days_in_month, iter_cycles


class AddMonthsTest(unittest.TestCase):
    def test_mid_month_anchor(self):
        self.assertEqual(add_months(date(2025, 3, 14), 1), date(2025, 4, 14))
        self.assertEqual(add_months(date(2025, 3, 14), 10), date(2026, 1, 14))

    def test_year_rollover(self):
        self.assertEqual(add_months(date(2025, 11, 5), 3), date(2026, 2, 5))
        self.assertEqual(add_months(date(2025, 12, 1), 12), date(2026, 12, 1))

    def test_month_end_anchor_clamps_then_returns(self):
        anchor = date(2026, 1, 31)
        got = [add_months(anchor, k) for k in range(1, 5)]
        self.assertEqual(got, [date(2026, 2, 28), date(2026, 3, 31),
                               date(2026, 4, 30), date(2026, 5, 31)])

    def test_leap_years(self):
        self.assertEqual(add_months(date(2028, 1, 30), 1), date(2028, 2, 29))
        anchor = date(2024, 2, 29)
        got = [add_months(anchor, 12 * k) for k in range(1, 5)]
        self.assertEqual(got, [date(2025, 2, 28), date(2026, 2, 28),
                               date(2027, 2, 28), date(2028, 2, 29)])

    def test_days_in_month(self):
        self.assertEqual(days_in_month(2026, 2), 28)
        self.assertEqual(days_in_month(2028, 2), 29)


class CycleBoundsTest(unittest.TestCase):
    def test_mid_month(self):
        self.assertEqual(cycle_bounds(date(2025, 3, 14), date(2026, 6, 20), "month"),
                         (date(2026, 6, 14), date(2026, 7, 14)))

    def test_change_on_renewal_day_starts_new_cycle(self):
        self.assertEqual(cycle_bounds(date(2025, 3, 14), date(2026, 6, 14), "month"),
                         (date(2026, 6, 14), date(2026, 7, 14)))

    def test_month_end_anchor(self):
        anchor = date(2024, 1, 31)
        self.assertEqual(cycle_bounds(anchor, date(2026, 2, 15), "month"),
                         (date(2026, 1, 31), date(2026, 2, 28)))
        self.assertEqual(cycle_bounds(anchor, date(2026, 3, 10), "month"),
                         (date(2026, 2, 28), date(2026, 3, 31)))

    def test_annual(self):
        self.assertEqual(cycle_bounds(date(2024, 2, 29), date(2027, 11, 2), "year"),
                         (date(2027, 2, 28), date(2028, 2, 29)))

    def test_iter_cycles_is_contiguous(self):
        cycles = list(iter_cycles(date(2026, 1, 31), date(2026, 6, 1), "month"))
        self.assertEqual(cycles[0][0], date(2026, 1, 31))
        for (s1, e1), (s2, _) in zip(cycles, cycles[1:]):
            self.assertEqual(e1, s2)
        self.assertEqual(cycles[-1], (date(2026, 5, 31), date(2026, 6, 30)))


if __name__ == "__main__":
    unittest.main()
