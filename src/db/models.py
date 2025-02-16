from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, String, Text, Uuid, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BigIntegerAsString(TypeDecorator):
    impl = String  # under the hood, this will create a TEXT column
    cache_ok = True  # recommended for SQLAlchemy 2.0+

    def process_bind_param(self, value: int | None, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: str | None, dialect: Any) -> int | None:
        if value is None:
            return None
        return int(value)


class Ledger(Base):
    __tablename__ = "ledger"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    external_id: Mapped[str | None]
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    in_currency: Mapped[str | None]
    in_amount: Mapped[int | None] = mapped_column(BigIntegerAsString)

    out_currency: Mapped[str | None]
    out_amount: Mapped[int | None] = mapped_column(BigIntegerAsString)

    fee: Mapped[int | None] = mapped_column(BigIntegerAsString)
    fee_currency: Mapped[str | None]

    operation_type: Mapped[str | None]
    operation_place: Mapped[str | None]

    note: Mapped[str | None] = mapped_column(Text)
    transactions: Mapped[list[str] | None] = mapped_column(JSON)


class Price(Base):
    __tablename__ = "prices"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    price_usd: Mapped[Decimal]
