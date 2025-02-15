from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import JSON, BigInteger, DateTime, String, Text, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Ledger(Base):
    __tablename__ = "ledger"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    currency_out: Mapped[str | None]
    amount_out: Mapped[int | None] = mapped_column(BigInteger)

    currency_in: Mapped[str | None]
    amount_in: Mapped[int | None] = mapped_column(BigInteger)

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
