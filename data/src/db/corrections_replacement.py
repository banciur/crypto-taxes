from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from db.corrections_common import CorrectionsBase
from db.models import DecimalAsString
from domain.correction import CorrectionId, Replacement
from domain.ledger import AccountChainId, AssetId, EventLocation, EventOrigin, LedgerLeg, LegId
from utils.misc import ensure_utc_datetime


class ReplacementCorrectionOrm(CorrectionsBase):
    __tablename__ = "replacement_corrections"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    legs: Mapped[list["ReplacementCorrectionLegOrm"]] = relationship(
        cascade="all, delete-orphan",
        back_populates="replacement_correction",
        lazy="joined",
    )
    sources: Mapped[list["ReplacementCorrectionSourceOrm"]] = relationship(
        cascade="all, delete-orphan",
        back_populates="replacement_correction",
        lazy="joined",
    )


class ReplacementCorrectionLegOrm(CorrectionsBase):
    __tablename__ = "replacement_correction_legs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    replacement_correction_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("replacement_corrections.id"),
        nullable=False,
    )
    asset_id: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(DecimalAsString, nullable=False)
    account_chain_id: Mapped[str] = mapped_column(String, nullable=False)
    is_fee: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    replacement_correction: Mapped[ReplacementCorrectionOrm] = relationship(back_populates="legs")


class ReplacementCorrectionSourceOrm(CorrectionsBase):
    __tablename__ = "replacement_correction_sources"

    replacement_correction_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("replacement_corrections.id"),
        primary_key=True,
        nullable=False,
    )
    origin_location: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)
    origin_external_id: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "origin_location",
            "origin_external_id",
            name="uq_replacement_correction_sources_origin",
        ),
        Index(
            "ix_replacement_correction_sources_origin",
            "origin_location",
            "origin_external_id",
        ),
    )

    replacement_correction: Mapped[ReplacementCorrectionOrm] = relationship(back_populates="sources")


class ReplacementCorrectionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, replacement: Replacement) -> Replacement:
        orm_replacement = ReplacementCorrectionOrm(
            id=replacement.id,
            timestamp=replacement.timestamp,
        )
        orm_replacement.legs = [
            ReplacementCorrectionLegOrm(
                id=leg.id,
                asset_id=leg.asset_id,
                quantity=leg.quantity,
                account_chain_id=leg.account_chain_id,
                is_fee=leg.is_fee,
            )
            for leg in replacement.legs
        ]
        orm_replacement.sources = [
            ReplacementCorrectionSourceOrm(
                origin_location=source.location.value,
                origin_external_id=source.external_id,
            )
            for source in replacement.sources
        ]
        self._session.add(orm_replacement)
        self._session.commit()
        return replacement

    def list(self) -> list[Replacement]:
        stmt = select(ReplacementCorrectionOrm).order_by(
            ReplacementCorrectionOrm.timestamp.asc(),
            ReplacementCorrectionOrm.id.asc(),
        )
        rows = self._session.execute(stmt).unique().scalars().all()
        return [self._to_domain(row) for row in rows]

    def delete(self, correction_id: CorrectionId) -> None:
        row = self._session.get(ReplacementCorrectionOrm, correction_id)
        if row is None:
            return
        self._session.delete(row)
        self._session.commit()

    @staticmethod
    def _to_domain(row: ReplacementCorrectionOrm) -> Replacement:
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
        return Replacement(
            id=CorrectionId(row.id),
            timestamp=ensure_utc_datetime(row.timestamp),
            legs=legs,
            sources=sources,
        )
