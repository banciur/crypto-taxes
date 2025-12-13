from decimal import Decimal
from random import choice
from string import ascii_lowercase


def generate_random_string(length: int) -> str:
    return "".join(choice(ascii_lowercase) for _ in range(length))


def decimal_to_int(d: Decimal, precision: int = 18) -> int:
    return int((d * (Decimal(10) ** precision)).to_integral_value(rounding="ROUND_HALF_UP"))


def int_to_decimal(value: int, precision: int = 18) -> Decimal:
    return Decimal(value) / (Decimal(10) ** precision)
