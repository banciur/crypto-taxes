from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, Uuid
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
    note: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    origin_location: Mapped[str] = mapped_column(String, nullable=False)
    origin_external_id: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (UniqueConstraint("origin_location", "origin_external_id", name="uq_ledger_events_origin"),)

    legs: Mapped[list["LedgerLegOrm"]] = relationship(
        cascade="all, delete-orphan", back_populates="event", lazy="joined"
    )


class LedgerLegOrm(Base):
    __tablename__ = "ledger_legs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("ledger_events.id"), nullable=False)
    asset_id: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(DecimalAsString, nullable=False)
    account_chain_id: Mapped[str] = mapped_column(String, nullable=False)
    is_fee: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    event: Mapped[LedgerEventOrm] = relationship(back_populates="legs")


class CorrectedLedgerEventOrm(Base):
    __tablename__ = "corrected_ledger_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingestion: Mapped[str] = mapped_column(String, nullable=False)
    note: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    origin_location: Mapped[str] = mapped_column(String, nullable=False)
    origin_external_id: Mapped[str] = mapped_column(String, nullable=False)

    legs: Mapped[list["CorrectedLedgerLegOrm"]] = relationship(
        cascade="all, delete-orphan", back_populates="event", lazy="joined"
    )


class CorrectedLedgerLegOrm(Base):
    __tablename__ = "corrected_ledger_legs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("corrected_ledger_events.id"), nullable=False)
    asset_id: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(DecimalAsString, nullable=False)
    account_chain_id: Mapped[str] = mapped_column(String, nullable=False)
    is_fee: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    event: Mapped["CorrectedLedgerEventOrm"] = relationship(back_populates="legs")


class AcquisitionLotOrm(Base):
    __tablename__ = "acquisition_lots"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    origin_location: Mapped[str] = mapped_column(String, nullable=False)
    origin_external_id: Mapped[str] = mapped_column(String, nullable=False)
    account_chain_id: Mapped[str] = mapped_column(String, nullable=False)
    asset_id: Mapped[str] = mapped_column(String, nullable=False)
    is_fee: Mapped[bool] = mapped_column(Boolean, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quantity_acquired: Mapped[Decimal] = mapped_column(DecimalAsString, nullable=False)
    cost_per_unit: Mapped[Decimal] = mapped_column(DecimalAsString, nullable=False)

    disposal_links: Mapped[list["DisposalLinkOrm"]] = relationship(back_populates="lot", cascade="all, delete-orphan")


class DisposalLinkOrm(Base):
    __tablename__ = "disposal_links"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    lot_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("acquisition_lots.id"), nullable=False)
    origin_location: Mapped[str] = mapped_column(String, nullable=False)
    origin_external_id: Mapped[str] = mapped_column(String, nullable=False)
    account_chain_id: Mapped[str] = mapped_column(String, nullable=False)
    asset_id: Mapped[str] = mapped_column(String, nullable=False)
    is_fee: Mapped[bool] = mapped_column(Boolean, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quantity_used: Mapped[Decimal] = mapped_column(DecimalAsString, nullable=False)
    proceeds_total: Mapped[Decimal] = mapped_column(DecimalAsString, nullable=False)

    lot: Mapped[AcquisitionLotOrm] = relationship(back_populates="disposal_links")


class TaxEventOrm(Base):
    __tablename__ = "tax_events"

    source_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    taxable_gain: Mapped[Decimal] = mapped_column(DecimalAsString, nullable=False)
