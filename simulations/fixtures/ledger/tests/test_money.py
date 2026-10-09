from decimal import Decimal

from ledger.money import round_cents


def test_rounds_a_third_decimal_below_five_down():
    assert round_cents(Decimal("1.234")) == Decimal("1.23")


def test_rounds_a_third_decimal_above_five_up():
    assert round_cents(Decimal("1.236")) == Decimal("1.24")


def test_keeps_two_decimals_on_a_whole_amount():
    assert round_cents(Decimal(7)) == Decimal("7.00")
