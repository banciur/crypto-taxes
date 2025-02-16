from decimal import Decimal


def decimal_to_int(d: Decimal, precision: int = 18) -> int:
    return int((d * (Decimal(10) ** precision)).to_integral_value(rounding="ROUND_HALF_UP"))


def int_to_decimal(value: int, precision: int = 18) -> Decimal:
    return Decimal(value) / (Decimal(10) ** precision)
