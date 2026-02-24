from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from corrections.spam import apply_spam_corrections
from domain.correction import Spam
from domain.ledger import EventLocation, EventOrigin, LedgerEvent, LedgerEventId, LedgerLeg
from tests.constants import BTC, KRAKEN_WALLET


def _raw_event(*, location: EventLocation, external_id: str, hour: int) -> LedgerEvent:
    return LedgerEvent(
        id=LedgerEventId(uuid4()),
        timestamp=datetime(2024, 1, 1, hour, 0, tzinfo=timezone.utc),
        origin=EventOrigin(location=location, external_id=external_id),
        ingestion="test",
        legs=[LedgerLeg(asset_id=BTC, quantity=Decimal("1"), account_chain_id=KRAKEN_WALLET, is_fee=False)],
    )


def test_filters_matching_spam_origin() -> None:
    kept = _raw_event(location=EventLocation.KRAKEN, external_id="keep", hour=1)
    spammed = _raw_event(location=EventLocation.ARBITRUM, external_id="0xspam", hour=2)

    filtered = apply_spam_corrections(
        raw_events=[kept, spammed],
        spam_markers=[Spam(event_origin=spammed.origin)],
    )

    assert filtered == [kept]


def test_preserves_order_of_remaining_events() -> None:
    first = _raw_event(location=EventLocation.KRAKEN, external_id="first", hour=1)
    second = _raw_event(location=EventLocation.BASE, external_id="second", hour=2)
    third = _raw_event(location=EventLocation.OPTIMISM, external_id="third", hour=3)

    filtered = apply_spam_corrections(
        raw_events=[first, second, third],
        spam_markers=[Spam(event_origin=second.origin)],
    )

    assert filtered == [first, third]


def test_handles_empty_and_duplicate_markers() -> None:
    first = _raw_event(location=EventLocation.ARBITRUM, external_id="0xa", hour=1)
    second = _raw_event(location=EventLocation.ETHEREUM, external_id="0xb", hour=2)
    duplicate_marker = Spam(event_origin=second.origin)

    no_spam_filtered = apply_spam_corrections(raw_events=[first, second], spam_markers=[])
    duplicate_filtered = apply_spam_corrections(
        raw_events=[first, second],
        spam_markers=[duplicate_marker, Spam(event_origin=second.origin)],
    )

    assert no_spam_filtered == [first, second]
    assert duplicate_filtered == [first]
