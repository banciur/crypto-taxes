from decimal import Decimal

from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator


class DecimalAsString(TypeDecorator):
    impl = String
    cache_ok = True

    def process_bind_param(self, value: Decimal | None, dialect: object) -> str | None:
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: str | None, dialect: object) -> Decimal | None:
        if value is None:
            return None
        return Decimal(value)


class Base(DeclarativeBase):
    pass
