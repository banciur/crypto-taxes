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
    acquisition_lots: Mapped[list["AcquisitionLotOrm"]] = relationship(
        cascade="all, delete-orphan", back_populates="acquired_event"
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
    acquired_lot: Mapped["AcquisitionLotOrm | None"] = relationship(back_populates="acquired_leg", uselist=False)
    disposal_links: Mapped[list["DisposalLinkOrm"]] = relationship(
        back_populates="disposal_leg", cascade="all, delete-orphan"
    )


class AcquisitionLotOrm(Base):
    __tablename__ = "acquisition_lots"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    acquired_event_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("ledger_events.id"), nullable=False)
    acquired_leg_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("ledger_legs.id"), nullable=False)
    cost_eur_per_unit: Mapped[Decimal] = mapped_column(DecimalAsString, nullable=False)

    acquired_event: Mapped[LedgerEventOrm] = relationship(
        back_populates="acquisition_lots", foreign_keys=[acquired_event_id]
    )
    acquired_leg: Mapped[LedgerLegOrm] = relationship(back_populates="acquired_lot", foreign_keys=[acquired_leg_id])
    disposal_links: Mapped[list["DisposalLinkOrm"]] = relationship(back_populates="lot", cascade="all, delete-orphan")


class DisposalLinkOrm(Base):
    __tablename__ = "disposal_links"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    disposal_leg_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("ledger_legs.id"), nullable=False)
    lot_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("acquisition_lots.id"), nullable=False)
    quantity_used: Mapped[Decimal] = mapped_column(DecimalAsString, nullable=False)
    proceeds_total_eur: Mapped[Decimal] = mapped_column(DecimalAsString, nullable=False)

    disposal_leg: Mapped[LedgerLegOrm] = relationship(back_populates="disposal_links", foreign_keys=[disposal_leg_id])
    lot: Mapped[AcquisitionLotOrm] = relationship(back_populates="disposal_links")
