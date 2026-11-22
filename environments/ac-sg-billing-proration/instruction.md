**BILL-212: wrong prorations for month-end and leap-day plan changes**

Support has a pile of complaints from customers who changed plan mid-cycle and got
an odd invoice. Almost all of them are on subscriptions anchored on the 29th, 30th or
31st, or on annual plans that started on 29 February. A couple are customers who moved
between monthly and annual billing.

The billing engine lives in `/app` (`billing/`). Finance has signed off the rules in
`docs/proration.md` (rev. 4) and turned the worst tickets into worked examples, which
are already wired into the test suite. Please fix the engine so plan changes are
prorated according to those rules.

Done means:

- `cd /app && python -m unittest discover -s tests` passes.
- `python -m billing preview ...` produces the right invoice for these customers.
- The public API of `billing.proration` and `billing.calendar` stays the same (other
  services import `prorate_change`, `cycle_bounds` and `add_months`).

When you're finished, give me a short summary of what was wrong and what you changed.
