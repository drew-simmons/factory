from collections.abc import Iterable
from decimal import Decimal

from ledger.money import round_cents
from ledger.parse import Transaction


def balance(transactions: Iterable[Transaction]) -> Decimal:
    """The closing balance: every amount summed, rounded to the cent."""
    return round_cents(sum((transaction.amount for transaction in transactions), Decimal(0)))


def totals_by_category(transactions: Iterable[Transaction]) -> dict[str, Decimal]:
    """Closing balance per category, in first-seen order."""
    totals: dict[str, Decimal] = {}
    for transaction in transactions:
        totals[transaction.category] = totals.get(transaction.category, Decimal(0)) + transaction.amount
    return {category: round_cents(total) for category, total in totals.items()}
