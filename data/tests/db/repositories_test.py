from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from db.repositories import AcquisitionLotRepository, DisposalLinkRepository, LedgerEventRepository, TaxEventRepository
from domain.base_types import EventLocation, LedgerLeg
from domain.ledger import (
    AcquisitionLot,
    DisposalId,
    DisposalLink,
    EventOrigin,
    EventType,
    LedgerEvent,
    LedgerEventId,
    LotId,
)
from domain.tax_event import TaxEvent, TaxEventKind
from tests.constants import BTC, EUR, KRAKEN_WALLET


def _sample_event(external_id: str, timestamp: datetime) -> LedgerEvent:
    return LedgerEvent(
        id=LedgerEventId(uuid4()),
        timestamp=timestamp,
        origin=EventOrigin(location=EventLocation.KRAKEN, external_id=external_id),
        ingestion="test_ingestion",
        event_type=EventType.TRADE,
        legs=[
            LedgerLeg(asset_id=BTC, quantity=Decimal("0.1"), wallet_id=KRAKEN_WALLET, is_fee=False),
            LedgerLeg(asset_id=EUR, quantity=Decimal("-2000"), wallet_id=KRAKEN_WALLET, is_fee=False),
        ],
    )


@pytest.fixture()
def repo(test_session: Session) -> LedgerEventRepository:
    return LedgerEventRepository(test_session)


@pytest.fixture()
def lot_repo(test_session: Session) -> AcquisitionLotRepository:
    return AcquisitionLotRepository(test_session)


@pytest.fixture()
def disposal_repo(test_session: Session) -> DisposalLinkRepository:
    return DisposalLinkRepository(test_session)


@pytest.fixture()
def tax_repo(test_session: Session) -> TaxEventRepository:
    return TaxEventRepository(test_session)


def test_create_and_get_ledger_event(repo: LedgerEventRepository) -> None:
    event = _sample_event("ext-1", datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc))

    created = repo.create(event)

    assert created.id == event.id
    assert created.timestamp == event.timestamp
    assert created.event_type == EventType.TRADE
    assert created.origin.location == EventLocation.KRAKEN
    assert len(created.legs) == 2
    assert {leg.asset_id for leg in created.legs} == {"BTC", "EUR"}

    fetched = repo.get(created.id)
    assert fetched == created


def test_list_ledger_events(repo: LedgerEventRepository) -> None:
    first = _sample_event("first-ext", datetime(2024, 1, 2, 15, 30, 0, tzinfo=timezone.utc))
    second = _sample_event("second-ext", datetime(2024, 1, 3, 8, 0, 0, tzinfo=timezone.utc))

    repo.create(first)
    repo.create(second)

    records = repo.list()

    fetched_ids = {record.id for record in records}
    assert fetched_ids == {first.id, second.id}


def test_persist_acquisition_lots(lot_repo: AcquisitionLotRepository, repo: LedgerEventRepository) -> None:
    acquisition_event = repo.create(_sample_event("acq-ext", datetime(2024, 1, 4, 9, 0, 0, tzinfo=timezone.utc)))
    lots = [
        AcquisitionLot(
            acquired_leg_id=acquisition_event.legs[0].id,
            cost_per_unit=Decimal("1.23"),
        ),
        AcquisitionLot(
            acquired_leg_id=acquisition_event.legs[1].id,
            cost_per_unit=Decimal("2.34"),
        ),
    ]

    saved = lot_repo.create_many(lots)
    assert {lot.id for lot in saved} == {lot.id for lot in lots}

    stored = lot_repo.list()
    stored_by_id = {lot.id: lot for lot in stored}
    for original in lots:
        reloaded = stored_by_id[original.id]
        assert reloaded.acquired_leg_id == original.acquired_leg_id
        assert reloaded.cost_per_unit == original.cost_per_unit


def test_persist_disposal_links(
    disposal_repo: DisposalLinkRepository, lot_repo: AcquisitionLotRepository, repo: LedgerEventRepository
) -> None:
    acquisition_event = repo.create(_sample_event("acq-ext", datetime(2024, 1, 4, 9, 0, 0, tzinfo=timezone.utc)))
    lots = [
        AcquisitionLot(
            acquired_leg_id=acquisition_event.legs[0].id,
            cost_per_unit=Decimal("1.23"),
        ),
        AcquisitionLot(
            acquired_leg_id=acquisition_event.legs[1].id,
            cost_per_unit=Decimal("2.34"),
        ),
    ]
    lot_repo.create_many(lots)

    disposal_event = repo.create(_sample_event("disposal-ext", datetime(2024, 1, 5, 10, 30, 0, tzinfo=timezone.utc)))
    disposal_leg_id = disposal_event.legs[0].id

    links = [
        DisposalLink(
            disposal_leg_id=disposal_leg_id,
            lot_id=lots[0].id,
            quantity_used=Decimal("0.5"),
            proceeds_total=Decimal("100"),
        ),
        DisposalLink(
            disposal_leg_id=disposal_leg_id,
            lot_id=lots[1].id,
            quantity_used=Decimal("1.25"),
            proceeds_total=Decimal("250.75"),
        ),
    ]

    saved = disposal_repo.create_many(links)
    assert {link.id for link in saved} == {link.id for link in links}

    stored = disposal_repo.list()
    stored_by_id = {link.id: link for link in stored}
    for original in links:
        reloaded = stored_by_id[original.id]
        assert reloaded.quantity_used == original.quantity_used
        assert reloaded.proceeds_total == original.proceeds_total


def test_persist_tax_events(tax_repo: TaxEventRepository) -> None:
    taxable_events = [
        TaxEvent(
            source_id=DisposalId(uuid4()),
            kind=TaxEventKind.DISPOSAL,
            taxable_gain=Decimal("123.45"),
        ),
        TaxEvent(
            source_id=LotId(uuid4()),
            kind=TaxEventKind.REWARD,
            taxable_gain=Decimal("67.89"),
        ),
    ]

    saved = tax_repo.create_many(taxable_events)
    assert {event.source_id for event in saved} == {event.source_id for event in taxable_events}

    stored = tax_repo.list()
    stored_by_source = {event.source_id: event for event in stored}
    for expected in taxable_events:
        reloaded = stored_by_source[expected.source_id]
        assert reloaded.kind == expected.kind
        assert reloaded.taxable_gain == expected.taxable_gain
