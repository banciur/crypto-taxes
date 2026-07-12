from datetime import datetime
from decimal import Decimal
from typing import Iterable
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, Uuid, select, tuple_
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from db.base import Base, DecimalAsString
from domain.ledger import (
    AccountChainId,
    AssetId,
    EventLocation,
    EventOrigin,
    LedgerEvent,
    LedgerEventId,
    LedgerLeg,
    LegId,
)
from utils.misc import ensure_utc_datetime


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

    event: Mapped[CorrectedLedgerEventOrm] = relationship(back_populates="legs")


class LedgerEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_many(self, events: list[LedgerEvent]) -> list[LedgerEvent]:
        orm_events: list[LedgerEventOrm] = []
        for event in events:
            orm_event = LedgerEventOrm(
                id=event.id,
                timestamp=event.timestamp,
                ingestion=event.ingestion,
                note=event.note,
                origin_location=event.event_origin.location.value,
                origin_external_id=event.event_origin.external_id,
            )
            orm_event.legs = [
                LedgerLegOrm(
                    id=leg.id,
                    asset_id=leg.asset_id,
                    quantity=leg.quantity,
                    account_chain_id=leg.account_chain_id,
                    is_fee=leg.is_fee,
                )
                for leg in event.legs
            ]
            orm_events.append(orm_event)

        self._session.add_all(orm_events)
        self._session.commit()
        return events

    def get(self, event_id: LedgerEventId) -> LedgerEvent | None:
        orm_event = self._session.get(LedgerEventOrm, event_id)
        if orm_event is None:
            return None
        return self._to_domain(orm_event)

    def list(self, asset_id: AssetId | None = None) -> list[LedgerEvent]:
        query = self._session.query(LedgerEventOrm)
        if asset_id is not None:
            # EXISTS over the legs, so a matching event keeps every leg, including its other assets.
            query = query.filter(LedgerEventOrm.legs.any(LedgerLegOrm.asset_id == asset_id))

        orm_events = query.order_by(
            LedgerEventOrm.timestamp.asc(),
            LedgerEventOrm.origin_location.asc(),
            LedgerEventOrm.origin_external_id.asc(),
        ).all()
        return [self._to_domain(event) for event in orm_events]

    def list_event_timestamps_for_origins(
        self, event_origins: Iterable[EventOrigin]
    ) -> Iterable[tuple[EventOrigin, datetime]]:
        origin_keys = list({(origin.location.value, origin.external_id) for origin in event_origins})
        if len(origin_keys) == 0:
            return []

        stmt = (
            select(
                LedgerEventOrm.origin_location,
                LedgerEventOrm.origin_external_id,
                LedgerEventOrm.timestamp,
            )
            .where(
                tuple_(
                    LedgerEventOrm.origin_location,
                    LedgerEventOrm.origin_external_id,
                ).in_(origin_keys)
            )
            .order_by(LedgerEventOrm.timestamp.asc())
        )
        rows = self._session.execute(stmt).all()
        return [
            (
                EventOrigin(location=EventLocation(origin_location), external_id=origin_external_id),
                ensure_utc_datetime(timestamp),
            )
            for origin_location, origin_external_id, timestamp in rows
        ]

    @staticmethod
    def _to_domain(orm_event: LedgerEventOrm) -> LedgerEvent:
        event_origin = EventOrigin(
            location=EventLocation(orm_event.origin_location), external_id=orm_event.origin_external_id
        )
        legs = [
            LedgerLeg(
                id=LegId(leg.id),
                asset_id=AssetId(leg.asset_id),
                quantity=leg.quantity,
                account_chain_id=AccountChainId(leg.account_chain_id),
                is_fee=leg.is_fee,
            )
            for leg in orm_event.legs
        ]
        return LedgerEvent(
            id=LedgerEventId(orm_event.id),
            timestamp=ensure_utc_datetime(orm_event.timestamp),
            event_origin=event_origin,
            ingestion=orm_event.ingestion,
            note=orm_event.note,
            legs=legs,
        )


class CorrectedLedgerEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_many(self, events: list[LedgerEvent]) -> list[LedgerEvent]:
        orm_events: list[CorrectedLedgerEventOrm] = []
        for event in events:
            orm_event = CorrectedLedgerEventOrm(
                id=event.id,
                timestamp=event.timestamp,
                ingestion=event.ingestion,
                note=event.note,
                origin_location=event.event_origin.location.value,
                origin_external_id=event.event_origin.external_id,
            )
            orm_event.legs = [
                CorrectedLedgerLegOrm(
                    id=leg.id,
                    asset_id=leg.asset_id,
                    quantity=leg.quantity,
                    account_chain_id=leg.account_chain_id,
                    is_fee=leg.is_fee,
                )
                for leg in event.legs
            ]
            orm_events.append(orm_event)

        self._session.add_all(orm_events)
        self._session.commit()
        return events

    def list(self, asset_id: AssetId | None = None) -> list[LedgerEvent]:
        query = self._session.query(CorrectedLedgerEventOrm)
        if asset_id is not None:
            query = query.filter(CorrectedLedgerEventOrm.legs.any(CorrectedLedgerLegOrm.asset_id == asset_id))

        orm_events = query.order_by(
            CorrectedLedgerEventOrm.timestamp.asc(),
            CorrectedLedgerEventOrm.origin_location.asc(),
            CorrectedLedgerEventOrm.origin_external_id.asc(),
        ).all()
        return [self._to_domain(event) for event in orm_events]

    @staticmethod
    def _to_domain(orm_event: CorrectedLedgerEventOrm) -> LedgerEvent:
        event_origin = EventOrigin(
            location=EventLocation(orm_event.origin_location), external_id=orm_event.origin_external_id
        )
        legs = [
            LedgerLeg(
                id=LegId(leg.id),
                asset_id=AssetId(leg.asset_id),
                quantity=leg.quantity,
                account_chain_id=AccountChainId(leg.account_chain_id),
                is_fee=leg.is_fee,
            )
            for leg in orm_event.legs
        ]
        return LedgerEvent(
            id=LedgerEventId(orm_event.id),
            timestamp=ensure_utc_datetime(orm_event.timestamp),
            event_origin=event_origin,
            ingestion=orm_event.ingestion,
            note=orm_event.note,
            legs=legs,
        )
