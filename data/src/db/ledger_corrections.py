from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Uuid, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from db.models import DecimalAsString
from domain.correction import CorrectionId, LedgerCorrection, LedgerCorrectionDraft
from domain.ledger import AccountChainId, AssetId, EventLocation, EventOrigin, LedgerLeg, LegId
from utils.misc import ensure_utc_datetime


class CorrectionsBase(DeclarativeBase):
    pass


class LedgerCorrectionOrm(CorrectionsBase):
    __tablename__ = "ledger_corrections"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price_per_token: Mapped[Decimal | None] = mapped_column(DecimalAsString, nullable=True)
    note: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    sources: Mapped[list["LedgerCorrectionSourceOrm"]] = relationship(
        cascade="all, delete-orphan",
        back_populates="correction",
        lazy="joined",
    )
    legs: Mapped[list["LedgerCorrectionLegOrm"]] = relationship(
        cascade="all, delete-orphan",
        back_populates="correction",
        lazy="joined",
    )


class LedgerCorrectionSourceOrm(CorrectionsBase):
    __tablename__ = "ledger_correction_sources"

    correction_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("ledger_corrections.id"), primary_key=True)
    origin_location: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)
    origin_external_id: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)

    __table_args__ = (
        Index(
            "ix_ledger_correction_sources_origin",
            "origin_location",
            "origin_external_id",
        ),
        Index(
            "uq_ledger_correction_sources_active_origin",
            "origin_location",
            "origin_external_id",
            unique=True,
        ),
    )

    correction: Mapped[LedgerCorrectionOrm] = relationship(back_populates="sources")


class LedgerCorrectionAutoSuppressionOrm(CorrectionsBase):
    __tablename__ = "ledger_correction_auto_suppressions"

    origin_location: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)
    origin_external_id: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)


class LedgerCorrectionLegOrm(CorrectionsBase):
    __tablename__ = "ledger_correction_legs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    correction_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("ledger_corrections.id"), nullable=False)
    asset_id: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(DecimalAsString, nullable=False)
    account_chain_id: Mapped[str] = mapped_column(String, nullable=False)
    is_fee: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    correction: Mapped[LedgerCorrectionOrm] = relationship(back_populates="legs")


class LedgerCorrectionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self) -> list[LedgerCorrection]:
        stmt = select(LedgerCorrectionOrm).order_by(LedgerCorrectionOrm.timestamp.desc(), LedgerCorrectionOrm.id.desc())
        rows = self._session.execute(stmt).unique().scalars().all()
        return [self._to_domain(row) for row in rows]

    def create(self, correction: LedgerCorrectionDraft) -> LedgerCorrection:
        orm_correction = LedgerCorrectionOrm(
            timestamp=correction.timestamp,
            price_per_token=correction.price_per_token,
            note=correction.note,
        )
        orm_correction.sources = [
            LedgerCorrectionSourceOrm(
                origin_location=source.location.value,
                origin_external_id=source.external_id,
            )
            for source in correction.sources
        ]
        orm_correction.legs = [
            LedgerCorrectionLegOrm(
                id=leg.id,
                asset_id=leg.asset_id,
                quantity=leg.quantity,
                account_chain_id=leg.account_chain_id,
                is_fee=leg.is_fee,
            )
            for leg in correction.legs
        ]
        self._session.add(orm_correction)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            raise
        return self._to_domain(orm_correction)

    def delete(self, correction_id: CorrectionId) -> None:
        row = self._session.get(LedgerCorrectionOrm, correction_id)
        if row is None:
            return

        for source in row.sources:
            self._ensure_auto_suppression(
                origin_location=source.origin_location,
                origin_external_id=source.origin_external_id,
            )
        self._session.delete(row)
        self._session.commit()

    def has_active_source(self, event_origin: EventOrigin) -> bool:
        stmt = select(LedgerCorrectionSourceOrm.correction_id).where(
            LedgerCorrectionSourceOrm.origin_location == event_origin.location.value,
            LedgerCorrectionSourceOrm.origin_external_id == event_origin.external_id,
        )
        return self._session.execute(stmt).scalar_one_or_none() is not None

    def is_auto_suppressed(self, event_origin: EventOrigin) -> bool:
        stmt = select(LedgerCorrectionAutoSuppressionOrm.origin_external_id).where(
            LedgerCorrectionAutoSuppressionOrm.origin_location == event_origin.location.value,
            LedgerCorrectionAutoSuppressionOrm.origin_external_id == event_origin.external_id,
        )
        return self._session.execute(stmt).scalar_one_or_none() is not None

    def _ensure_auto_suppression(self, *, origin_location: str, origin_external_id: str) -> None:
        existing = self._session.get(
            LedgerCorrectionAutoSuppressionOrm,
            (origin_location, origin_external_id),
        )
        if existing is None:
            self._session.add(
                LedgerCorrectionAutoSuppressionOrm(
                    origin_location=origin_location,
                    origin_external_id=origin_external_id,
                )
            )

    @staticmethod
    def _to_domain(row: LedgerCorrectionOrm) -> LedgerCorrection:
        sources = [
            EventOrigin(
                location=EventLocation(source.origin_location),
                external_id=source.origin_external_id,
            )
            for source in sorted(
                row.sources,
                key=lambda source: (source.origin_location, source.origin_external_id),
            )
        ]
        legs = [
            LedgerLeg(
                id=LegId(leg.id),
                asset_id=AssetId(leg.asset_id),
                quantity=leg.quantity,
                account_chain_id=AccountChainId(leg.account_chain_id),
                is_fee=leg.is_fee,
            )
            for leg in sorted(row.legs, key=lambda leg: leg.id)
        ]
        return LedgerCorrection(
            id=CorrectionId(row.id),
            timestamp=ensure_utc_datetime(row.timestamp),
            sources=frozenset(sources),
            legs=frozenset(legs),
            price_per_token=row.price_per_token,
            note=row.note,
        )
