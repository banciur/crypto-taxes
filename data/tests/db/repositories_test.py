from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from db.repositories import (
    AcquisitionLotRepository,
    CorrectedLedgerEventRepository,
    DisposalLinkRepository,
    LedgerEventRepository,
    SeedEventRepository,
    TaxEventRepository,
)
from domain.correction import SeedEvent
from domain.ledger import (
    AcquisitionLot,
    DisposalId,
    DisposalLink,
    EventLocation,
    EventOrigin,
    LedgerEvent,
    LedgerEventId,
    LedgerLeg,
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


@pytest.fixture()
def seed_repo(test_session: Session) -> SeedEventRepository:
    return SeedEventRepository(test_session)


@pytest.fixture()
def corrected_repo(test_session: Session) -> CorrectedLedgerEventRepository:
    return CorrectedLedgerEventRepository(test_session)


def test_create_and_get_ledger_event(repo: LedgerEventRepository) -> None:
    event = _sample_event("ext-1", datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc))

    repo.create_many([event])

    fetched = repo.get(event.id)
    assert fetched is not None
    assert fetched.id == event.id
    assert fetched.timestamp == event.timestamp
    assert fetched.origin.location == event.origin.location
    assert len(fetched.legs) == len(event.legs)
    assert {leg.asset_id for leg in fetched.legs} == {leg.asset_id for leg in event.legs}


def test_list_ledger_events(repo: LedgerEventRepository) -> None:
    first = _sample_event("first-ext", datetime(2024, 1, 2, 15, 30, 0, tzinfo=timezone.utc))
    second = _sample_event("second-ext", datetime(2024, 1, 3, 8, 0, 0, tzinfo=timezone.utc))

    repo.create_many([first, second])

    records = repo.list()

    fetched_ids = {record.id for record in records}
    assert fetched_ids == {first.id, second.id}


def test_persist_acquisition_lots(lot_repo: AcquisitionLotRepository, repo: LedgerEventRepository) -> None:
    acquisition_event = _sample_event("acq-ext", datetime(2024, 1, 4, 9, 0, 0, tzinfo=timezone.utc))
    repo.create_many([acquisition_event])
    stored_acquisition_event = repo.get(acquisition_event.id)
    assert stored_acquisition_event is not None

    lots = [
        AcquisitionLot(
            acquired_leg_id=stored_acquisition_event.legs[0].id,
            cost_per_unit=Decimal("1.23"),
        ),
        AcquisitionLot(
            acquired_leg_id=stored_acquisition_event.legs[1].id,
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
    acquisition_event = _sample_event("acq-ext", datetime(2024, 1, 4, 9, 0, 0, tzinfo=timezone.utc))
    repo.create_many([acquisition_event])
    stored_acquisition_event = repo.get(acquisition_event.id)
    assert stored_acquisition_event is not None

    lots = [
        AcquisitionLot(
            acquired_leg_id=stored_acquisition_event.legs[0].id,
            cost_per_unit=Decimal("1.23"),
        ),
        AcquisitionLot(
            acquired_leg_id=stored_acquisition_event.legs[1].id,
            cost_per_unit=Decimal("2.34"),
        ),
    ]
    lot_repo.create_many(lots)

    disposal_event = _sample_event("disposal-ext", datetime(2024, 1, 5, 10, 30, 0, tzinfo=timezone.utc))
    repo.create_many([disposal_event])
    stored_disposal_event = repo.get(disposal_event.id)
    assert stored_disposal_event is not None

    disposal_leg_id = stored_disposal_event.legs[0].id

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


def test_persist_seed_events(seed_repo: SeedEventRepository) -> None:
    timestamp = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    price_per_token = Decimal("1.23")
    quantity = Decimal("0.5")
    seed_event = SeedEvent(
        timestamp=timestamp,
        price_per_token=price_per_token,
        legs=[LedgerLeg(asset_id=BTC, quantity=quantity, wallet_id=KRAKEN_WALLET, is_fee=False)],
    )

    seed_repo.create_many([seed_event])

    stored = seed_repo.list()
    assert len(stored) == 1
    (reloaded,) = stored
    assert reloaded.id == seed_event.id
    assert reloaded.timestamp == timestamp
    assert reloaded.price_per_token == price_per_token
    assert len(reloaded.legs) == 1
    (leg,) = reloaded.legs
    assert leg.asset_id == BTC
    assert leg.quantity == quantity
    assert leg.wallet_id == KRAKEN_WALLET


def test_persist_corrected_ledger_events(corrected_repo: CorrectedLedgerEventRepository) -> None:
    external_id = "corrected-ext"
    timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    event = _sample_event(external_id, timestamp)

    corrected_repo.create_many([event])

    stored = corrected_repo.list()
    assert len(stored) == 1
    (reloaded,) = stored
    assert reloaded.id == event.id
    assert reloaded.timestamp == timestamp
    assert reloaded.origin.external_id == external_id
    assert {leg.id for leg in reloaded.legs} == {leg.id for leg in event.legs}
