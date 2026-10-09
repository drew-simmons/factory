from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

FIELD_COUNT = 4


@dataclass(frozen=True)
class Transaction:
    posted_on: date
    category: str
    description: str
    amount: Decimal


class LedgerFormatError(ValueError):
    """A ledger line does not have the shape date,category,description,amount."""


def parse_ledger(text: str) -> list[Transaction]:
    """Parse ledger text, one transaction per line, skipping blank lines."""
    return [parse_line(line, number) for number, line in enumerate(text.splitlines(), 1) if line.strip()]


def parse_line(line: str, number: int) -> Transaction:
    fields = [field.strip() for field in line.split(",")]
    if len(fields) != FIELD_COUNT:
        raise LedgerFormatError(f"line {number}: expected {FIELD_COUNT} fields, got {len(fields)}: {line!r}")
    posted_on_text, category, description, amount_text = fields
    try:
        posted_on = date.fromisoformat(posted_on_text)
        amount = Decimal(amount_text)
    except (ValueError, InvalidOperation) as error:
        raise LedgerFormatError(f"line {number}: {error}: {line!r}") from error
    return Transaction(posted_on, category, description, amount)
