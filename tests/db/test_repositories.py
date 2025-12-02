from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from db.repositories import LedgerEventRepository
from domain.ledger import EventLocation, EventOrigin, EventType, LedgerEvent, LedgerLeg


def _sample_event(external_id: str, timestamp: datetime) -> LedgerEvent:
    return LedgerEvent(
        id=uuid4(),
        timestamp=timestamp,
        origin=EventOrigin(location=EventLocation.KRAKEN, external_id=external_id),
        ingestion="test_ingestion",
        event_type=EventType.TRADE,
        legs=[
            LedgerLeg(asset_id="BTC", quantity=Decimal("0.1"), wallet_id="kraken", is_fee=False),
            LedgerLeg(asset_id="EUR", quantity=Decimal("-2000"), wallet_id="kraken", is_fee=False),
        ],
    )


@pytest.fixture()
def repo(test_session: Session) -> LedgerEventRepository:
    return LedgerEventRepository(test_session)


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
