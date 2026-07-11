from collections import defaultdict
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import String, UniqueConstraint, Uuid, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from db.base import DecimalAsString
from db.mixins import TimestampAuditMixin
from domain.ledger import AssetId, EventLocation, EventOrigin
from domain.price_override import PriceOverride, PriceOverrideDraft, PriceOverrideId


class PriceOverridesBase(DeclarativeBase):
    pass


class PriceOverrideOrm(TimestampAuditMixin, PriceOverridesBase):
    __tablename__ = "price_overrides"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    origin_location: Mapped[str] = mapped_column(String, nullable=False)
    origin_external_id: Mapped[str] = mapped_column(String, nullable=False)
    asset_id: Mapped[str] = mapped_column(String, nullable=False)
    rate_eur: Mapped[Decimal] = mapped_column(DecimalAsString, nullable=False)
    note: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    __table_args__ = (
        UniqueConstraint(
            "origin_location",
            "origin_external_id",
            "asset_id",
            name="uq_price_overrides_origin_asset",
        ),
    )


class PriceOverrideRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self) -> list[PriceOverride]:
        stmt = select(PriceOverrideOrm).order_by(
            PriceOverrideOrm.created_at.desc(),
            PriceOverrideOrm.id.desc(),
        )
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_domain(row) for row in rows]

    def rates_by_origin(self) -> dict[EventOrigin, dict[AssetId, Decimal]]:
        rates: dict[EventOrigin, dict[AssetId, Decimal]] = defaultdict(dict)
        for override in self.list():
            rates[override.event_origin][override.asset_id] = override.rate_eur
        return dict(rates)

    def create(self, override: PriceOverrideDraft) -> PriceOverride:
        orm_override = PriceOverrideOrm(
            origin_location=override.event_origin.location.value,
            origin_external_id=override.event_origin.external_id,
            asset_id=override.asset_id,
            rate_eur=override.rate_eur,
            note=override.note,
            **PriceOverrideOrm.new_timestamp_audit_values(),
        )
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
        return PriceOverride(
            id=PriceOverrideId(row.id),
            event_origin=EventOrigin(
                location=EventLocation(row.origin_location),
                external_id=row.origin_external_id,
            ),
            asset_id=AssetId(row.asset_id),
            rate_eur=row.rate_eur,
            note=row.note,
        )
