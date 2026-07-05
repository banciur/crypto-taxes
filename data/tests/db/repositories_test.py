from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from accounts import KRAKEN_ACCOUNT_ID
from db.acquisition_disposal import AcquisitionDisposalProjectionRepository
from db.ledger_events import CorrectedLedgerEventRepository, LedgerEventRepository
from db.tax_events import TaxEventRepository
from domain.acquisition_disposal.models import AcquisitionLot, DisposalLink
from domain.acquisition_disposal.projector import AcquisitionDisposalProjection
from domain.ledger import (
    DisposalId,
    EventLocation,
    EventOrigin,
    LedgerEvent,
    LedgerEventId,
    LedgerLeg,
    LotId,
)
from domain.tax_event import TaxEvent, TaxEventKind
from tests.constants import BTC, EUR


def _sample_event(external_id: str, timestamp: datetime, *, note: str | None = None) -> LedgerEvent:
    return LedgerEvent(
        id=LedgerEventId(uuid4()),
        timestamp=timestamp,
        event_origin=EventOrigin(location=EventLocation.KRAKEN, external_id=external_id),
        ingestion="test_ingestion",
        note=note,
        legs=[
            LedgerLeg(asset_id=BTC, quantity=Decimal("0.1"), account_chain_id=KRAKEN_ACCOUNT_ID, is_fee=False),
            LedgerLeg(asset_id=EUR, quantity=Decimal("-2000"), account_chain_id=KRAKEN_ACCOUNT_ID, is_fee=False),
        ],
    )


def _acquisition_lot_from_event(event: LedgerEvent, *, leg_index: int, cost_per_unit: Decimal) -> AcquisitionLot:
    leg = event.legs[leg_index]
    quantity_acquired = leg.quantity if leg.quantity > 0 else abs(leg.quantity)
    return AcquisitionLot(
        event_origin=event.event_origin,
        account_chain_id=leg.account_chain_id,
        asset_id=leg.asset_id,
        is_fee=leg.is_fee,
        timestamp=event.timestamp,
        quantity_acquired=quantity_acquired,
        cost_per_unit=cost_per_unit,
    )


def _disposal_link_from_event(
    event: LedgerEvent,
    *,
    leg_index: int,
    lot_id: LotId,
    quantity_used: Decimal,
    proceeds_total: Decimal,
) -> DisposalLink:
    leg = event.legs[leg_index]
    return DisposalLink(
        event_origin=event.event_origin,
        account_chain_id=leg.account_chain_id,
        asset_id=leg.asset_id,
        is_fee=leg.is_fee,
        timestamp=event.timestamp,
        lot_id=lot_id,
        quantity_used=quantity_used,
        proceeds_total=proceeds_total,
    )


@pytest.fixture()
def repo(test_session: Session) -> LedgerEventRepository:
    return LedgerEventRepository(test_session)


@pytest.fixture()
def tax_repo(test_session: Session) -> TaxEventRepository:
    return TaxEventRepository(test_session)


@pytest.fixture()
def projection_repo(test_session: Session) -> AcquisitionDisposalProjectionRepository:
    return AcquisitionDisposalProjectionRepository(test_session)


@pytest.fixture()
def corrected_repo(test_session: Session) -> CorrectedLedgerEventRepository:
    return CorrectedLedgerEventRepository(test_session)


def test_create_and_get_ledger_event(repo: LedgerEventRepository) -> None:
    note = "approve"
    event = _sample_event("ext-1", datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc), note=note)

    repo.create_many([event])

    fetched = repo.get(event.id)
    assert fetched is not None
    assert fetched.id == event.id
    assert fetched.timestamp == event.timestamp
    assert fetched.event_origin.location == event.event_origin.location
    assert fetched.note == note
    assert len(fetched.legs) == len(event.legs)
    assert {leg.asset_id for leg in fetched.legs} == {leg.asset_id for leg in event.legs}


def test_list_ledger_events(repo: LedgerEventRepository) -> None:
    first = _sample_event("first-ext", datetime(2024, 1, 2, 15, 30, 0, tzinfo=timezone.utc))
    second = _sample_event("second-ext", datetime(2024, 1, 3, 8, 0, 0, tzinfo=timezone.utc))

    repo.create_many([first, second])

    records = repo.list()

    fetched_ids = {record.id for record in records}
    assert fetched_ids == {first.id, second.id}


def test_list_event_timestamps_for_origins(repo: LedgerEventRepository) -> None:
    first = _sample_event("first-ext", datetime(2024, 1, 2, 15, 30, 0, tzinfo=timezone.utc))
    ignored = _sample_event("ignored-ext", datetime(2024, 1, 2, 16, 30, 0, tzinfo=timezone.utc))
    second = _sample_event("second-ext", datetime(2024, 1, 3, 8, 0, 0, tzinfo=timezone.utc))

    repo.create_many([second, ignored, first])

    matches = list(repo.list_event_timestamps_for_origins([second.event_origin, first.event_origin]))

    assert matches == [
        (first.event_origin, first.timestamp),
        (second.event_origin, second.timestamp),
    ]


def test_create_many_rejects_duplicate_event_origins(repo: LedgerEventRepository) -> None:
    first = _sample_event("duplicate-ext", datetime(2024, 1, 2, 15, 30, 0, tzinfo=timezone.utc))
    second = _sample_event("duplicate-ext", datetime(2024, 1, 3, 8, 0, 0, tzinfo=timezone.utc))

    with pytest.raises(IntegrityError):
        repo.create_many([first, second])


def test_replace_acquisition_disposal_projection(projection_repo: AcquisitionDisposalProjectionRepository) -> None:
    acquisition_event = _sample_event("acq-ext", datetime(2024, 1, 4, 9, 0, 0, tzinfo=timezone.utc))
    disposal_event = _sample_event("disposal-ext", datetime(2024, 1, 5, 10, 30, 0, tzinfo=timezone.utc))
    lots = [
        _acquisition_lot_from_event(acquisition_event, leg_index=0, cost_per_unit=Decimal("1.23")),
        _acquisition_lot_from_event(acquisition_event, leg_index=1, cost_per_unit=Decimal("2.34")),
    ]
    links = [
        _disposal_link_from_event(
            disposal_event,
            leg_index=0,
            lot_id=lots[0].id,
            quantity_used=Decimal("0.5"),
            proceeds_total=Decimal("100"),
        ),
        _disposal_link_from_event(
            disposal_event,
            leg_index=0,
            lot_id=lots[1].id,
            quantity_used=Decimal("1.25"),
            proceeds_total=Decimal("250.75"),
        ),
    ]
    projection = AcquisitionDisposalProjection(acquisition_lots=lots, disposal_links=links)

    saved = projection_repo.replace(projection)

    assert saved == projection
    stored = projection_repo.get()
    assert {lot.id: lot for lot in stored.acquisition_lots} == {lot.id: lot for lot in lots}
    assert {link.id: link for link in stored.disposal_links} == {link.id: link for link in links}


def test_replace_acquisition_disposal_projection_clears_previous_rows(
    projection_repo: AcquisitionDisposalProjectionRepository,
) -> None:
    first_acquisition_event = _sample_event("first-acq-ext", datetime(2024, 1, 4, 9, 0, 0, tzinfo=timezone.utc))
    first_disposal_event = _sample_event("first-disposal-ext", datetime(2024, 1, 5, 10, 30, 0, tzinfo=timezone.utc))
    stale_lot = _acquisition_lot_from_event(first_acquisition_event, leg_index=0, cost_per_unit=Decimal("1.23"))
    stale_link = _disposal_link_from_event(
        first_disposal_event,
        leg_index=0,
        lot_id=stale_lot.id,
        quantity_used=Decimal("0.5"),
        proceeds_total=Decimal("100"),
    )
    projection_repo.replace(AcquisitionDisposalProjection(acquisition_lots=[stale_lot], disposal_links=[stale_link]))

    replacement_event = _sample_event("replacement-acq-ext", datetime(2024, 1, 6, 9, 0, 0, tzinfo=timezone.utc))
    replacement_lot = _acquisition_lot_from_event(replacement_event, leg_index=0, cost_per_unit=Decimal("4.56"))
    projection_repo.replace(AcquisitionDisposalProjection(acquisition_lots=[replacement_lot], disposal_links=[]))

    stored = projection_repo.get()
    assert stored.acquisition_lots == [replacement_lot]
    assert stored.disposal_links == []


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


def test_persist_corrected_ledger_events(corrected_repo: CorrectedLedgerEventRepository) -> None:
    external_id = "corrected-ext"
    timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    note = "depositAll"
    event = _sample_event(external_id, timestamp, note=note)

    corrected_repo.create_many([event])

    stored = corrected_repo.list()
    assert len(stored) == 1
    (reloaded,) = stored
    assert reloaded.id == event.id
    assert reloaded.timestamp == timestamp
    assert reloaded.event_origin.external_id == external_id
    assert reloaded.note == note
    assert {leg.id for leg in reloaded.legs} == {leg.id for leg in event.legs}


def test_list_corrected_ledger_events_uses_canonical_order(corrected_repo: CorrectedLedgerEventRepository) -> None:
    timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    base_event = LedgerEvent(
        id=LedgerEventId(uuid4()),
        timestamp=timestamp,
        event_origin=EventOrigin(location=EventLocation.BASE, external_id="b-ext"),
        ingestion="z-ingestion",
        note=None,
        legs=[
            LedgerLeg(
                asset_id=BTC,
                quantity=Decimal("0.1"),
                account_chain_id=KRAKEN_ACCOUNT_ID,
                is_fee=False,
            )
        ],
    )
    ethereum_event = LedgerEvent(
        id=LedgerEventId(uuid4()),
        timestamp=timestamp,
        event_origin=EventOrigin(location=EventLocation.ETHEREUM, external_id="a-ext"),
        ingestion="a-ingestion",
        note=None,
        legs=[
            LedgerLeg(
                asset_id=BTC,
                quantity=Decimal("0.2"),
                account_chain_id=KRAKEN_ACCOUNT_ID,
                is_fee=False,
            )
        ],
    )
    kraken_event = LedgerEvent(
        id=LedgerEventId(uuid4()),
        timestamp=timestamp,
        event_origin=EventOrigin(location=EventLocation.KRAKEN, external_id="a-ext"),
        ingestion="m-ingestion",
        note=None,
        legs=[
            LedgerLeg(
                asset_id=BTC,
                quantity=Decimal("0.3"),
                account_chain_id=KRAKEN_ACCOUNT_ID,
                is_fee=False,
            )
        ],
    )

    corrected_repo.create_many([kraken_event, base_event, ethereum_event])

    stored = corrected_repo.list()

    assert [(event.event_origin.location, event.event_origin.external_id) for event in stored] == [
        (EventLocation.BASE, "b-ext"),
        (EventLocation.ETHEREUM, "a-ext"),
        (EventLocation.KRAKEN, "a-ext"),
    ]
