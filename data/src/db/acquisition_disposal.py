from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid, delete
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from db.base import Base, DecimalAsString
from domain.acquisition_disposal.models import AcquisitionLot, DisposalLink
from domain.acquisition_disposal.projector import AcquisitionDisposalProjection
from domain.ledger import AccountChainId, AssetId, DisposalId, EventLocation, EventOrigin, LotId
from utils.misc import ensure_utc_datetime


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


class AcquisitionDisposalProjectionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace(self, projection: AcquisitionDisposalProjection) -> AcquisitionDisposalProjection:
        self._session.execute(delete(DisposalLinkOrm))
        self._session.execute(delete(AcquisitionLotOrm))
        self._session.flush()
        self._session.expunge_all()

        self._session.add_all([self._lot_to_orm(lot) for lot in projection.acquisition_lots])
        self._session.flush()
        self._session.add_all([self._link_to_orm(link) for link in projection.disposal_links])
        self._session.commit()
        return projection

    def get(self) -> AcquisitionDisposalProjection:
        orm_lots = (
            self._session.query(AcquisitionLotOrm)
            .order_by(
                AcquisitionLotOrm.timestamp.asc(),
                AcquisitionLotOrm.origin_location.asc(),
                AcquisitionLotOrm.origin_external_id.asc(),
                AcquisitionLotOrm.id.asc(),
            )
            .all()
        )
        orm_links = (
            self._session.query(DisposalLinkOrm)
            .order_by(
                DisposalLinkOrm.timestamp.asc(),
                DisposalLinkOrm.origin_location.asc(),
                DisposalLinkOrm.origin_external_id.asc(),
                DisposalLinkOrm.id.asc(),
            )
            .all()
        )
        return AcquisitionDisposalProjection(
            acquisition_lots=[self._lot_to_domain(lot) for lot in orm_lots],
            disposal_links=[self._link_to_domain(link) for link in orm_links],
        )

    @staticmethod
    def _lot_to_orm(lot: AcquisitionLot) -> AcquisitionLotOrm:
        return AcquisitionLotOrm(
            id=lot.id,
            origin_location=lot.event_origin.location.value,
            origin_external_id=lot.event_origin.external_id,
            account_chain_id=lot.account_chain_id,
            asset_id=lot.asset_id,
            is_fee=lot.is_fee,
            timestamp=lot.timestamp,
            quantity_acquired=lot.quantity_acquired,
            cost_per_unit=lot.cost_per_unit,
        )

    @staticmethod
    def _link_to_orm(link: DisposalLink) -> DisposalLinkOrm:
        return DisposalLinkOrm(
            id=link.id,
            lot_id=link.lot_id,
            origin_location=link.event_origin.location.value,
            origin_external_id=link.event_origin.external_id,
            account_chain_id=link.account_chain_id,
            asset_id=link.asset_id,
            is_fee=link.is_fee,
            timestamp=link.timestamp,
            quantity_used=link.quantity_used,
            proceeds_total=link.proceeds_total,
        )

    @staticmethod
    def _lot_to_domain(lot: AcquisitionLotOrm) -> AcquisitionLot:
        return AcquisitionLot(
            id=LotId(lot.id),
            event_origin=EventOrigin(
                location=EventLocation(lot.origin_location),
                external_id=lot.origin_external_id,
            ),
            account_chain_id=AccountChainId(lot.account_chain_id),
            asset_id=AssetId(lot.asset_id),
            is_fee=lot.is_fee,
            timestamp=ensure_utc_datetime(lot.timestamp),
            quantity_acquired=lot.quantity_acquired,
            cost_per_unit=lot.cost_per_unit,
        )

    @staticmethod
    def _link_to_domain(link: DisposalLinkOrm) -> DisposalLink:
        return DisposalLink(
            id=DisposalId(link.id),
            lot_id=LotId(link.lot_id),
            event_origin=EventOrigin(
                location=EventLocation(link.origin_location),
                external_id=link.origin_external_id,
            ),
            account_chain_id=AccountChainId(link.account_chain_id),
            asset_id=AssetId(link.asset_id),
            is_fee=link.is_fee,
            timestamp=ensure_utc_datetime(link.timestamp),
            quantity_used=link.quantity_used,
            proceeds_total=link.proceeds_total,
        )
