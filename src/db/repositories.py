from __future__ import annotations

from datetime import timezone
from uuid import UUID

from sqlalchemy.orm import Session

from db import models
from domain.ledger import EventLocation, EventOrigin, EventType, LedgerEvent, LedgerLeg


class LedgerEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, event: LedgerEvent) -> LedgerEvent:
        orm_event = models.LedgerEventOrm(
            id=event.id,
            timestamp=event.timestamp,
            ingestion=event.ingestion,
            event_type=event.event_type.value,
            origin_location=event.origin.location.value,
            origin_external_id=event.origin.external_id,
        )
        orm_event.legs = [
            models.LedgerLegOrm(
                id=leg.id,
                asset_id=leg.asset_id,
                quantity=leg.quantity,
                wallet_id=leg.wallet_id,
                is_fee=leg.is_fee,
            )
            for leg in event.legs
        ]

        self._session.add(orm_event)
        self._session.commit()
        self._session.refresh(orm_event)
        return self._to_domain(orm_event)

    def get(self, event_id: UUID) -> LedgerEvent | None:
        orm_event = self._session.get(models.LedgerEventOrm, event_id)
        if orm_event is None:
            return None
        return self._to_domain(orm_event)

    def list(self) -> list[LedgerEvent]:
        orm_events = self._session.query(models.LedgerEventOrm).order_by(models.LedgerEventOrm.timestamp.asc()).all()
        return [self._to_domain(event) for event in orm_events]

    @staticmethod
    def _to_domain(orm_event: models.LedgerEventOrm) -> LedgerEvent:
        timestamp = orm_event.timestamp
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        origin = EventOrigin(
            location=EventLocation(orm_event.origin_location), external_id=orm_event.origin_external_id
        )
        legs = [
            LedgerLeg(
                id=leg.id,
                asset_id=leg.asset_id,
                quantity=leg.quantity,
                wallet_id=leg.wallet_id,
                is_fee=leg.is_fee,
            )
            for leg in orm_event.legs
        ]
        return LedgerEvent(
            id=orm_event.id,
            timestamp=timestamp,
            origin=origin,
            ingestion=orm_event.ingestion,
            event_type=EventType(orm_event.event_type),
            legs=legs,
        )
