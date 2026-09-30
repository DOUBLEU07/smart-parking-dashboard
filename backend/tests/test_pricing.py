from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.pricing import PricingRule, calculate_fee, fee_for_minutes

RULE = PricingRule(free_minutes=15, hourly_rate=Decimal("20"), daily_cap=Decimal("200"))


@pytest.mark.parametrize(
    ("minutes", "hours", "amount"),
    [
        (0, 0, 0),
        (15, 0, 0),  # free period is inclusive
        (16, 1, 20),
        (60, 1, 20),
        (61, 2, 40),
        (600, 10, 200),  # 10 h hits the daily cap
        (660, 11, 200),
        (24 * 60, 24, 200),  # one full day
        (24 * 60 + 1, 25, 220),  # one day + a started hour
        (48 * 60 + 11 * 60, 59, 600),  # two days + capped remainder
    ],
)
def test_fee_table(minutes, hours, amount):
    q = fee_for_minutes(minutes, RULE)
    assert q.billable_hours == hours
    assert q.amount == Decimal(amount)


def test_no_cap():
    rule = PricingRule(0, Decimal("30"), None)
    assert fee_for_minutes(25 * 60, rule).amount == Decimal("750")


def test_seconds_round_up_to_minutes():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    assert calculate_fee(start, start + timedelta(minutes=15, seconds=1), RULE).amount == Decimal("20")
    assert calculate_fee(start, start - timedelta(minutes=5), RULE).amount == Decimal("0")
