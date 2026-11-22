"""Invoice previews for plan changes."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List

from .proration import Line, Proration

CURRENCY_EXPONENT = {"USD": 2, "EUR": 2, "GBP": 2, "JPY": 0}


@dataclass
class InvoicePreview:
    sub_id: str
    currency: str
    issued_on: date
    lines: List[Line] = field(default_factory=list)
    balance_before: int = 0

    @property
    def subtotal(self) -> int:
        return sum(line.amount for line in self.lines)

    @property
    def amount_due(self) -> int:
        """What the customer pays now; never negative."""
        return max(0, self.subtotal + self.balance_before)

    @property
    def credit_carried(self) -> int:
        """Credit left on the account after this invoice (positive number)."""
        return max(0, -(self.subtotal + self.balance_before))


def build_preview(proration: Proration, currency: str, balance_before: int = 0) -> InvoicePreview:
    return InvoicePreview(
        sub_id=proration.sub_id,
        currency=currency,
        issued_on=proration.change_at,
        lines=list(proration.lines),
        balance_before=balance_before,
    )


def format_amount(minor: int, currency: str) -> str:
    exp = CURRENCY_EXPONENT.get(currency, 2)
    sign = "-" if minor < 0 else ""
    minor = abs(minor)
    if exp == 0:
        return f"{sign}{minor} {currency}"
    major, frac = divmod(minor, 10 ** exp)
    return f"{sign}{major:,}.{frac:0{exp}d} {currency}"


def to_dict(preview: InvoicePreview) -> Dict:
    return {
        "subscription": preview.sub_id,
        "currency": preview.currency,
        "issued_on": preview.issued_on.isoformat(),
        "lines": [
            {
                "kind": line.kind,
                "plan": line.plan_id,
                "amount": line.amount,
                "period_start": line.period_start.isoformat(),
                "period_end": line.period_end.isoformat(),
                "description": line.description,
            }
            for line in preview.lines
        ],
        "subtotal": preview.subtotal,
        "balance_before": preview.balance_before,
        "amount_due": preview.amount_due,
        "credit_carried": preview.credit_carried,
    }


def render_text(preview: InvoicePreview) -> str:
    out = [f"Invoice preview for {preview.sub_id} ({preview.issued_on})"]
    for line in preview.lines:
        out.append(f"  {line.description:<60} {format_amount(line.amount, preview.currency):>16}")
    out.append(f"  {'Subtotal':<60} {format_amount(preview.subtotal, preview.currency):>16}")
    if preview.balance_before:
        out.append(f"  {'Balance before':<60} {format_amount(preview.balance_before, preview.currency):>16}")
    out.append(f"  {'Amount due':<60} {format_amount(preview.amount_due, preview.currency):>16}")
    if preview.credit_carried:
        out.append(f"  {'Credit carried forward':<60} {format_amount(preview.credit_carried, preview.currency):>16}")
    return "\n".join(out)
