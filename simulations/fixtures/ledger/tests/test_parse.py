from datetime import date
from decimal import Decimal

import pytest

from ledger.parse import LedgerFormatError, Transaction, parse_ledger

LEDGER = """
2026-09-03, groceries, market, -42.10
2026-09-05, salary, september, 2500.00

2026-10-01, groceries, bakery, -3.50
"""


def test_parses_one_transaction_per_non_blank_line():
    transactions = parse_ledger(LEDGER)
    assert transactions[0] == Transaction(date(2026, 9, 3), "groceries", "market", Decimal("-42.10"))
    assert len(transactions) == 3


def test_rejects_a_line_with_the_wrong_field_count():
    with pytest.raises(LedgerFormatError, match="line 1: expected 4 fields, got 3"):
        parse_ledger("2026-09-03, groceries, -42.10")


def test_rejects_an_unparseable_date_with_the_line_number():
    with pytest.raises(LedgerFormatError, match="line 2"):
        parse_ledger("2026-09-03, a, b, 1\nyesterday, a, b, 1")


def test_rejects_an_unparseable_amount():
    with pytest.raises(LedgerFormatError, match="line 1"):
        parse_ledger("2026-09-03, a, b, twelve")
