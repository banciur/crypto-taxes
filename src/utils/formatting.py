from __future__ import annotations

from decimal import Decimal


def format_decimal(value: Decimal) -> str:
    quantized = value.normalize()
    # Avoid scientific notation for integers.
    if quantized == quantized.to_integral():
        return f"{quantized:.0f}"
    return format(quantized, "f")


def format_currency(value: Decimal) -> str:
    cents = value.quantize(Decimal("0.01"))
    return f"{cents:.2f}"
