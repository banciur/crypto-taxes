from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
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


class LedgerEventOrm(Base):
    __tablename__ = "ledger_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingestion: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    origin_location: Mapped[str] = mapped_column(String, nullable=False)
    origin_external_id: Mapped[str] = mapped_column(String, nullable=False)

    legs: Mapped[list["LedgerLegOrm"]] = relationship(
        cascade="all, delete-orphan", back_populates="event", lazy="joined"
    )


class LedgerLegOrm(Base):
    __tablename__ = "ledger_legs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("ledger_events.id"), nullable=False)
    asset_id: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(DecimalAsString, nullable=False)
    wallet_id: Mapped[str] = mapped_column(String, nullable=False)
    is_fee: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    event: Mapped[LedgerEventOrm] = relationship(back_populates="legs")
