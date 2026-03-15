from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.corrections_common import CorrectionsBase
from db.models import DecimalAsString


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
