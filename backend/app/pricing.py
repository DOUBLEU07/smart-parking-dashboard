"""Parking fee rules.

- Stays up to `free_minutes` (inclusive) are free.
- Otherwise every started hour is charged at `hourly_rate` (rounded up).
- With `daily_cap`, each full 24 hours costs at most the cap, and the
  remaining hours are charged at most the cap as well.
"""

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class PricingRule:
    free_minutes: int
    hourly_rate: Decimal
    daily_cap: Decimal | None


@dataclass(frozen=True)
class FeeQuote:
    duration_minutes: int
    billable_hours: int
    amount: Decimal


def fee_for_minutes(minutes: int, rule: PricingRule) -> FeeQuote:
    minutes = max(0, minutes)
    if minutes <= rule.free_minutes:
        return FeeQuote(minutes, 0, Decimal("0"))

    hours = math.ceil(minutes / 60)
    if rule.daily_cap is None:
        amount = hours * rule.hourly_rate
    else:
        days, rest = divmod(hours, 24)
        amount = days * rule.daily_cap + min(rest * rule.hourly_rate, rule.daily_cap)
    return FeeQuote(minutes, hours, Decimal(amount).quantize(Decimal("0.01")))


def calculate_fee(entry: datetime, exit_: datetime, rule: PricingRule) -> FeeQuote:
    seconds = max(0.0, (exit_ - entry).total_seconds())
    return fee_for_minutes(math.ceil(seconds / 60), rule)
