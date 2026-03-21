from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Uuid, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from db.corrections_common import CorrectionsBase
from db.models import DecimalAsString
from domain.correction import CorrectionId, LedgerCorrection
from domain.ledger import AccountChainId, AssetId, EventLocation, EventOrigin, LedgerLeg, LegId
from utils.misc import ensure_utc_datetime


class LedgerCorrectionOrm(CorrectionsBase):
    __tablename__ = "ledger_corrections"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price_per_token: Mapped[Decimal | None] = mapped_column(DecimalAsString, nullable=True)
    note: Mapped[str] = mapped_column(String, nullable=False, default="")
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

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
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

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
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    correction: Mapped[LedgerCorrectionOrm] = relationship(back_populates="sources")


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
        stmt = (
            select(LedgerCorrectionOrm)
            .where(LedgerCorrectionOrm.is_deleted.is_(False))
            .order_by(LedgerCorrectionOrm.timestamp.desc(), LedgerCorrectionOrm.id.desc())
        )
        rows = self._session.execute(stmt).unique().scalars().all()
        return [self._to_domain(row) for row in rows]

    def create(self, correction: LedgerCorrection) -> LedgerCorrection:
        orm_correction = LedgerCorrectionOrm(
            id=correction.id,
            timestamp=correction.timestamp,
            price_per_token=correction.price_per_token,
            note=correction.note,
            is_deleted=False,
        )
        orm_correction.sources = [
            LedgerCorrectionSourceOrm(
                origin_location=source.location.value,
                origin_external_id=source.external_id,
                is_deleted=False,
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
        return correction

    def delete(self, correction_id: CorrectionId) -> None:
        row = self._session.get(LedgerCorrectionOrm, correction_id)
        if row is None:
            return

        if len(row.sources) == 0:
            self._session.delete(row)
        else:
            row.is_deleted = True
            for source in row.sources:
                source.is_deleted = True

        self._session.commit()

    def has_source(self, event_origin: EventOrigin, *, include_deleted: bool = False) -> bool:
        stmt = select(LedgerCorrectionSourceOrm).where(
            LedgerCorrectionSourceOrm.origin_location == event_origin.location.value,
            LedgerCorrectionSourceOrm.origin_external_id == event_origin.external_id,
        )
        if not include_deleted:
            stmt = stmt.where(LedgerCorrectionSourceOrm.is_deleted.is_(False))
        return self._session.execute(stmt.limit(1)).scalar_one_or_none() is not None

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
            if source.is_deleted is False
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
            sources=sources,
            legs=legs,
            price_per_token=row.price_per_token,
            note=row.note,
        )
