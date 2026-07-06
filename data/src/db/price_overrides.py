from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String, Uuid, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from db.base import DecimalAsString
from db.mixins import TimestampAuditMixin
from db.session import init_db_session
from domain.ledger import AssetId, EventLocation, EventOrigin
from domain.price_override import PriceOverride, PriceOverrideDraft, PriceOverrideId


class PriceOverridesBase(DeclarativeBase):
    pass


class PriceOverrideOrm(TimestampAuditMixin, PriceOverridesBase):
    __tablename__ = "price_overrides"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    asset_id: Mapped[str] = mapped_column(String, nullable=False)
    rate_eur: Mapped[Decimal] = mapped_column(DecimalAsString, nullable=False)
    note: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    sources: Mapped[list["PriceOverrideSourceOrm"]] = relationship(
        cascade="all, delete-orphan",
        back_populates="override",
        lazy="joined",
    )


class PriceOverrideSourceOrm(PriceOverridesBase):
    __tablename__ = "price_override_sources"

    override_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("price_overrides.id"), primary_key=True)
    origin_location: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)
    origin_external_id: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)

    __table_args__ = (
        # Non-unique: unlike correction sources, one raw origin may back several overrides (e.g. one
        # per asset in the same event), so resolution looks up owners without a uniqueness guarantee.
        Index("ix_price_override_sources_origin", "origin_location", "origin_external_id"),
    )

    override: Mapped[PriceOverrideOrm] = relationship(back_populates="sources")


def init_price_overrides_db(*, db_path: Path, echo: bool = False, reset: bool = False) -> Session:
    return init_db_session(
        db_path=db_path,
        metadata=PriceOverridesBase.metadata,
        echo=echo,
        reset=reset,
    )


class PriceOverrideRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self) -> list[PriceOverride]:
        stmt = select(PriceOverrideOrm).order_by(
            PriceOverrideOrm.created_at.desc(),
            PriceOverrideOrm.id.desc(),
        )
        rows = self._session.execute(stmt).unique().scalars().all()
        return [self._to_domain(row) for row in rows]

    def create(self, override: PriceOverrideDraft) -> PriceOverride:
        orm_override = PriceOverrideOrm(
            asset_id=override.asset_id,
            rate_eur=override.rate_eur,
            note=override.note,
            **PriceOverrideOrm.new_timestamp_audit_values(),
        )
        orm_override.sources = [
            PriceOverrideSourceOrm(
                origin_location=source.location.value,
                origin_external_id=source.external_id,
            )
            for source in override.sources
        ]
        self._session.add(orm_override)
        self._session.commit()
        return self._to_domain(orm_override)

    def delete(self, override_id: PriceOverrideId) -> None:
        row = self._session.get(PriceOverrideOrm, override_id)
        if row is None:
            return
        self._session.delete(row)
        self._session.commit()

    @staticmethod
    def _to_domain(row: PriceOverrideOrm) -> PriceOverride:
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
        return PriceOverride(
            id=PriceOverrideId(row.id),
            sources=frozenset(sources),
            asset_id=AssetId(row.asset_id),
            rate_eur=row.rate_eur,
            note=row.note,
        )
