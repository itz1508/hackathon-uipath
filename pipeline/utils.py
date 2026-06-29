"""Utility helpers for the pipeline (small, dependency-free)."""
from decimal import Decimal, ROUND_HALF_UP


def to_hundredths(value: float) -> int:
    """Convert a floating score (0-100) to integer hundredths deterministically.

    Examples:
        93.909 -> 9391 (if rounded half up)
    """
    dec = Decimal(str(value)) * Decimal(100)
    rounded = int(dec.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    return rounded
