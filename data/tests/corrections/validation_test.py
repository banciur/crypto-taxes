# This file is completely vibed and I didn't read it.
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from corrections.validation import CorrectionValidationError, validate_ingestion_corrections
from domain.correction import Replacement, Spam
from domain.ledger import EventLocation, EventOrigin, LedgerEvent, LedgerEventId, LedgerLeg
from tests.constants import BTC, ETH, KRAKEN_WALLET, LEDGER_WALLET


def _raw_event(*, location: EventLocation, external_id: str, hour: int) -> LedgerEvent:
    return LedgerEvent(
        id=LedgerEventId(uuid4()),
        timestamp=datetime(2024, 1, 1, hour, 0, tzinfo=timezone.utc),
        event_origin=EventOrigin(location=location, external_id=external_id),
        ingestion="raw_ingestion",
        legs=[LedgerLeg(asset_id=BTC, quantity=Decimal("1"), account_chain_id=KRAKEN_WALLET, is_fee=False)],
    )


def _replacement(*, timestamp_hour: int, sources: list[EventOrigin]) -> Replacement:
    return Replacement(
        timestamp=datetime(2024, 1, 1, timestamp_hour, 30, tzinfo=timezone.utc),
        sources=sources,
        legs=[
            LedgerLeg(asset_id=BTC, quantity=Decimal("-0.1"), account_chain_id=KRAKEN_WALLET),
            LedgerLeg(asset_id=BTC, quantity=Decimal("0.09995"), account_chain_id=LEDGER_WALLET),
            LedgerLeg(asset_id=ETH, quantity=Decimal("-0.001"), account_chain_id=KRAKEN_WALLET, is_fee=True),
        ],
    )


def test_validate_ingestion_corrections_accepts_non_overlapping_sources() -> None:
    raw_events = [
        _raw_event(location=EventLocation.ETHEREUM, external_id="0xsend", hour=10),
        _raw_event(location=EventLocation.COINBASE, external_id="cb-receive", hour=11),
    ]
    replacements = [_replacement(timestamp_hour=11, sources=[raw_events[0].event_origin])]
    spam_markers = [Spam(event_origin=raw_events[1].event_origin)]

    validate_ingestion_corrections(
        raw_events=raw_events,
        spam_markers=spam_markers,
        replacements=replacements,
    )


def test_validate_ingestion_corrections_fails_on_missing_replacement_source() -> None:
    raw_events = [_raw_event(location=EventLocation.ETHEREUM, external_id="0xpresent", hour=10)]
    missing_origin = EventOrigin(location=EventLocation.COINBASE, external_id="cb-missing")
    replacements = [_replacement(timestamp_hour=11, sources=[missing_origin])]

    with pytest.raises(
        CorrectionValidationError,
        match="Replacement source must match exactly one raw event: COINBASE/cb-missing",
    ):
        validate_ingestion_corrections(
            raw_events=raw_events,
            spam_markers=[],
            replacements=replacements,
        )


def test_validate_ingestion_corrections_fails_on_spam_replacement_overlap() -> None:
    overlapped_raw_event = _raw_event(location=EventLocation.ETHEREUM, external_id="0xshared", hour=10)
    replacements = [_replacement(timestamp_hour=11, sources=[overlapped_raw_event.event_origin])]
    spam_markers = [Spam(event_origin=overlapped_raw_event.event_origin)]

    with pytest.raises(
        CorrectionValidationError,
        match="Raw event cannot be both spam and replacement source: ETHEREUM/0xshared",
    ):
        validate_ingestion_corrections(
            raw_events=[overlapped_raw_event],
            spam_markers=spam_markers,
            replacements=replacements,
        )


def test_validate_ingestion_corrections_fails_on_duplicate_replacement_consumption() -> None:
    shared_raw_event = _raw_event(location=EventLocation.ETHEREUM, external_id="0xshared", hour=10)
    replacements = [
        _replacement(timestamp_hour=11, sources=[shared_raw_event.event_origin]),
        _replacement(timestamp_hour=12, sources=[shared_raw_event.event_origin]),
    ]

    with pytest.raises(
        CorrectionValidationError,
        match="Raw event cannot be consumed by more than one replacement source: ETHEREUM/0xshared",
    ):
        validate_ingestion_corrections(
            raw_events=[shared_raw_event],
            spam_markers=[],
            replacements=replacements,
        )
