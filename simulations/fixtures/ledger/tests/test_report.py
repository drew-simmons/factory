from datetime import date
from decimal import Decimal

from ledger.parse import Transaction
from ledger.report import balance, totals_by_category

TRANSACTIONS = [
    Transaction(date(2026, 9, 3), "groceries", "market", Decimal("-42.10")),
    Transaction(date(2026, 9, 5), "salary", "september", Decimal("2500.00")),
    Transaction(date(2026, 10, 1), "groceries", "bakery", Decimal("-3.50")),
]


def test_balance_sums_every_amount():
    assert balance(TRANSACTIONS) == Decimal("2454.40")


def test_balance_of_nothing_is_zero_cents():
    assert balance([]) == Decimal("0.00")


def test_totals_group_by_category_in_first_seen_order():
    assert totals_by_category(TRANSACTIONS) == {
        "groceries": Decimal("-45.60"),
        "salary": Decimal("2500.00"),
    }
