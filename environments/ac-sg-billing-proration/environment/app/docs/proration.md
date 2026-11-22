# Proration rules (finance sign-off, rev. 4)

These are the rules the billing engine must follow when a subscription changes
plan part-way through a billing cycle. Amounts are integers in minor units
(cents for USD).

## 1. Billing cycles

A subscription has an **anchor date**: the day it was first billed. Monthly
plans renew every calendar month, annual plans every twelve calendar months.

Renewal *k* is the anchor moved forward by *k* (monthly) or *12k* (annual)
calendar months. If the target month does not have the anchor's day of month,
the renewal falls on the **last day of that month**. Every renewal is computed
from the original anchor, never from the previous renewal, so a cycle that was
shortened by a short month returns to the anchor day afterwards.

| anchor     | interval | renewals                                         |
|------------|----------|--------------------------------------------------|
| 2026-01-31 | month    | 2026-02-28, 2026-03-31, 2026-04-30, 2026-05-31 … |
| 2028-01-30 | month    | 2028-02-29, 2028-03-30, 2028-04-30 …             |
| 2024-02-29 | year     | 2025-02-28, 2026-02-28, 2027-02-28, 2028-02-29 … |

The cycle containing a date *d* is the half-open interval `[start, end)` where
`start` is the latest renewal (or the anchor) on or before *d* and `end` is the
next renewal. A change made on a renewal date belongs to the cycle that starts
that day.

## 2. Credit for the old plan

`period_days = end - start` and `remaining_days = end - change_date`, both in
whole days. The credit is

    credit = round_half_even(old_price * remaining_days / period_days)

where `old_price` is the old plan's price **in force on the cycle start** (that
is what the customer was billed). Rounding is half-to-even to a whole minor
unit, applied once to the exact rational result.

## 3. Charge for the new plan

* **Same interval** (month to month, year to year): the customer keeps the
  same anchor and pays for the rest of the current cycle:
  `charge = round_half_even(new_price * remaining_days / period_days)`, with
  `new_price` in force on the change date. The next renewal stays `end`.
* **Different interval** (month to year or year to month): the subscription is
  re-anchored on the change date. The customer pays the new plan's full price
  in force on the change date, the new anchor is the change date and the next
  renewal is one new-interval later (computed with the rule in section 1).

## 4. Invoice

The preview has a negative credit line and a positive charge line. The total
is `charge - credit`; a negative total is carried forward as account credit.
