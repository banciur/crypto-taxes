from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from db import models
from domain.ledger import (
    AccountChainId,
    AcquisitionLot,
    AssetId,
    DisposalId,
    DisposalLink,
    EventLocation,
    EventOrigin,
    LedgerEvent,
    LedgerEventId,
    LedgerLeg,
    LegId,
    LotId,
)
from domain.tax_event import TaxEvent, TaxEventKind
from utils.misc import ensure_utc_datetime


class LedgerEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_many(self, events: list[LedgerEvent]) -> list[LedgerEvent]:
        orm_events: list[models.LedgerEventOrm] = []
        for event in events:
            orm_event = models.LedgerEventOrm(
                id=event.id,
                timestamp=event.timestamp,
                ingestion=event.ingestion,
                note=event.note,
                origin_location=event.event_origin.location.value,
                origin_external_id=event.event_origin.external_id,
            )
            orm_event.legs = [
                models.LedgerLegOrm(
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
        orm_event = self._session.get(models.LedgerEventOrm, event_id)
        if orm_event is None:
            return None
        return self._to_domain(orm_event)

    def list(self) -> list[LedgerEvent]:
        orm_events = self._session.query(models.LedgerEventOrm).order_by(models.LedgerEventOrm.timestamp.asc()).all()
        return [self._to_domain(event) for event in orm_events]

    def list_event_timestamps_for_origins(
        self, event_origins: Iterable[EventOrigin]
    ) -> Iterable[tuple[EventOrigin, datetime]]:
        origin_keys = list({(origin.location.value, origin.external_id) for origin in event_origins})
        if len(origin_keys) == 0:
            return []

        stmt = (
            select(
                models.LedgerEventOrm.origin_location,
                models.LedgerEventOrm.origin_external_id,
                models.LedgerEventOrm.timestamp,
            )
            .where(
                tuple_(
                    models.LedgerEventOrm.origin_location,
                    models.LedgerEventOrm.origin_external_id,
                ).in_(origin_keys)
            )
            .order_by(models.LedgerEventOrm.timestamp.asc())
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
    def _to_domain(orm_event: models.LedgerEventOrm) -> LedgerEvent:
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
        orm_events: list[models.CorrectedLedgerEventOrm] = []
        for event in events:
            orm_event = models.CorrectedLedgerEventOrm(
                id=event.id,
                timestamp=event.timestamp,
                ingestion=event.ingestion,
                note=event.note,
                origin_location=event.event_origin.location.value,
                origin_external_id=event.event_origin.external_id,
            )
            orm_event.legs = [
                models.CorrectedLedgerLegOrm(
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

    def list(self) -> list[LedgerEvent]:
        orm_events = (
            self._session.query(models.CorrectedLedgerEventOrm)
            .order_by(models.CorrectedLedgerEventOrm.timestamp.asc())
            .all()
        )
        return [self._to_domain(event) for event in orm_events]

    @staticmethod
    def _to_domain(orm_event: models.CorrectedLedgerEventOrm) -> LedgerEvent:
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


class AcquisitionLotRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_many(self, lots: list[AcquisitionLot]) -> list[AcquisitionLot]:
        orm_lots = [
            models.AcquisitionLotOrm(
                id=lot.id,
                acquired_leg_id=lot.acquired_leg_id,
                cost_per_unit=lot.cost_per_unit,
            )
            for lot in lots
        ]
        self._session.add_all(orm_lots)
        self._session.commit()
        return lots

    def list(self) -> list[AcquisitionLot]:
        orm_lots = self._session.query(models.AcquisitionLotOrm).all()
        return [
            AcquisitionLot(
                id=LotId(lot.id),
                acquired_leg_id=LegId(lot.acquired_leg_id),
                cost_per_unit=lot.cost_per_unit,
            )
            for lot in orm_lots
        ]


class DisposalLinkRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_many(self, links: list[DisposalLink]) -> list[DisposalLink]:
        orm_links = [
            models.DisposalLinkOrm(
                id=link.id,
                disposal_leg_id=link.disposal_leg_id,
                lot_id=link.lot_id,
                quantity_used=link.quantity_used,
                proceeds_total=link.proceeds_total,
            )
            for link in links
        ]
        self._session.add_all(orm_links)
        self._session.commit()
        return links

    def list(self) -> list[DisposalLink]:
        orm_links = self._session.query(models.DisposalLinkOrm).all()
        return [
            DisposalLink(
                id=DisposalId(link.id),
                disposal_leg_id=LegId(link.disposal_leg_id),
                lot_id=LotId(link.lot_id),
                quantity_used=link.quantity_used,
                proceeds_total=link.proceeds_total,
            )
            for link in orm_links
        ]


class TaxEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_many(self, tax_events: list[TaxEvent]) -> list[TaxEvent]:
        orm_events = [
            models.TaxEventOrm(
                source_id=tax_event.source_id,
                kind=tax_event.kind.value,
                taxable_gain=tax_event.taxable_gain,
            )
            for tax_event in tax_events
        ]
        self._session.add_all(orm_events)
        self._session.commit()
        return tax_events

    def list(self) -> list[TaxEvent]:
        orm_events = self._session.query(models.TaxEventOrm).all()
        persisted: list[TaxEvent] = []
        for tax_event in orm_events:
            kind = TaxEventKind(tax_event.kind)
            source_id: DisposalId | LotId
            if kind == TaxEventKind.DISPOSAL:
                source_id = DisposalId(tax_event.source_id)
            else:
                source_id = LotId(tax_event.source_id)

            persisted.append(TaxEvent(source_id=source_id, kind=kind, taxable_gain=tax_event.taxable_gain))
        return persisted
