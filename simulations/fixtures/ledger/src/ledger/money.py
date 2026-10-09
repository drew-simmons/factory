from decimal import ROUND_HALF_EVEN, Decimal

CENT = Decimal("0.01")


def round_cents(amount: Decimal) -> Decimal:
    """Round an amount to whole cents the way statements print it."""
    return amount.quantize(CENT, rounding=ROUND_HALF_EVEN)
