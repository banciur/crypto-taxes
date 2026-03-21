from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from accounts import KRAKEN_ACCOUNT_ID
from corrections.ingestion import apply_ingestion_corrections
from corrections.ledger_corrections import LEDGER_CORRECTION_INGESTION, ledger_event_from_correction
from corrections.validation import CorrectionValidationError, validate_ingestion_corrections
from domain.correction import LedgerCorrection
from domain.ledger import AccountChainId, EventLocation, EventOrigin, LedgerEvent, LedgerEventId, LedgerLeg
from tests.constants import BTC, ETH, LEDGER_WALLET


def _raw_event(
    *,
    location: EventLocation,
    external_id: str,
    hour: int,
    quantity: Decimal,
    account_chain_id: AccountChainId,
) -> LedgerEvent:
    return LedgerEvent(
        id=LedgerEventId(uuid4()),
        timestamp=datetime(2024, 1, 1, hour, 0, tzinfo=timezone.utc),
        event_origin=EventOrigin(location=location, external_id=external_id),
        ingestion="raw_ingestion",
        legs=[LedgerLeg(asset_id=BTC, quantity=quantity, account_chain_id=account_chain_id)],
    )


def test_apply_ingestion_corrections_handles_discard_replacement_and_opening_balance() -> None:
    discarded = _raw_event(
        location=EventLocation.ARBITRUM,
        external_id="0xdiscard",
        hour=2,
        quantity=Decimal("1"),
        account_chain_id=KRAKEN_ACCOUNT_ID,
    )
    replaced_sent = _raw_event(
        location=EventLocation.ETHEREUM,
        external_id="0xsend",
        hour=3,
        quantity=Decimal("-0.1"),
        account_chain_id=KRAKEN_ACCOUNT_ID,
    )
    replaced_received = _raw_event(
        location=EventLocation.COINBASE,
        external_id="cb-receive",
        hour=4,
        quantity=Decimal("0.09995"),
        account_chain_id=LEDGER_WALLET,
    )
    kept = _raw_event(
        location=EventLocation.KRAKEN,
        external_id="kraken-keep",
        hour=5,
        quantity=Decimal("0.25"),
        account_chain_id=KRAKEN_ACCOUNT_ID,
    )

    opening_balance = LedgerCorrection(
        timestamp=datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        legs=frozenset([LedgerLeg(asset_id=BTC, quantity=Decimal("0.5"), account_chain_id=LEDGER_WALLET)]),
        price_per_token=Decimal("0"),
    )
    discard = LedgerCorrection(
        timestamp=discarded.timestamp,
        sources=frozenset([discarded.event_origin]),
    )
    replacement = LedgerCorrection(
        timestamp=datetime(2024, 1, 1, 4, 30, tzinfo=timezone.utc),
        sources=frozenset([replaced_sent.event_origin, replaced_received.event_origin]),
        legs=frozenset(
            [
                LedgerLeg(asset_id=BTC, quantity=Decimal("-0.1"), account_chain_id=KRAKEN_ACCOUNT_ID),
                LedgerLeg(asset_id=BTC, quantity=Decimal("0.09995"), account_chain_id=LEDGER_WALLET),
                LedgerLeg(
                    asset_id=ETH,
                    quantity=Decimal("-0.001"),
                    account_chain_id=KRAKEN_ACCOUNT_ID,
                    is_fee=True,
                ),
            ]
        ),
    )

    corrected = apply_ingestion_corrections(
        raw_events=[discarded, kept, replaced_sent, replaced_received],
        corrections=[discard, replacement, opening_balance],
    )

    assert [event.event_origin.external_id for event in corrected] == [
        str(opening_balance.id),
        str(replacement.id),
        kept.event_origin.external_id,
    ]
    assert corrected[0].ingestion == LEDGER_CORRECTION_INGESTION
    assert corrected[1].ingestion == LEDGER_CORRECTION_INGESTION
    assert corrected[0].event_origin.location == EventLocation.INTERNAL
    assert corrected[1].event_origin.location == EventLocation.INTERNAL


def test_ledger_event_from_correction_uses_unified_provenance() -> None:
    correction = LedgerCorrection(
        timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        legs=frozenset([LedgerLeg(asset_id=BTC, quantity=Decimal("1"), account_chain_id=LEDGER_WALLET)]),
    )

    event = ledger_event_from_correction(correction)

    assert event.timestamp == correction.timestamp
    assert event.event_origin.location == EventLocation.INTERNAL
    assert event.event_origin.external_id == str(correction.id)
    assert event.ingestion == LEDGER_CORRECTION_INGESTION
    assert frozenset(event.legs) == correction.legs


def test_validate_ingestion_corrections_rejects_missing_source() -> None:
    raw_events = [
        _raw_event(
            location=EventLocation.ETHEREUM,
            external_id="0xpresent",
            hour=10,
            quantity=Decimal("1"),
            account_chain_id=KRAKEN_ACCOUNT_ID,
        )
    ]
    correction = LedgerCorrection(
        timestamp=datetime(2024, 1, 1, 10, 30, tzinfo=timezone.utc),
        sources=frozenset([EventOrigin(location=EventLocation.COINBASE, external_id="cb-missing")]),
    )

    with pytest.raises(
        CorrectionValidationError,
        match="Correction source must match exactly one raw event: COINBASE/cb-missing",
    ):
        validate_ingestion_corrections(raw_events=raw_events, corrections=[correction])


def test_validate_ingestion_corrections_rejects_duplicate_consumption() -> None:
    raw_event = _raw_event(
        location=EventLocation.ETHEREUM,
        external_id="0xshared",
        hour=10,
        quantity=Decimal("1"),
        account_chain_id=KRAKEN_ACCOUNT_ID,
    )
    first = LedgerCorrection(timestamp=raw_event.timestamp, sources=frozenset([raw_event.event_origin]))
    second = LedgerCorrection(
        timestamp=datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc),
        sources=frozenset([raw_event.event_origin]),
        legs=frozenset([LedgerLeg(asset_id=BTC, quantity=Decimal("1"), account_chain_id=LEDGER_WALLET)]),
    )

    with pytest.raises(
        CorrectionValidationError,
        match="Raw event cannot be consumed by more than one correction source: ETHEREUM/0xshared",
    ):
        validate_ingestion_corrections(raw_events=[raw_event], corrections=[first, second])


def test_source_less_correction_requires_positive_non_fee_single_leg() -> None:
    with pytest.raises(ValueError, match="Source-less LedgerCorrection requires exactly one leg"):
        LedgerCorrection(
            timestamp=datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
            legs=frozenset(
                [
                    LedgerLeg(asset_id=BTC, quantity=Decimal("1"), account_chain_id=LEDGER_WALLET),
                    LedgerLeg(asset_id=ETH, quantity=Decimal("1"), account_chain_id=LEDGER_WALLET),
                ]
            ),
        )

    with pytest.raises(ValueError, match="Source-less LedgerCorrection leg must be positive"):
        LedgerCorrection(
            timestamp=datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
            legs=frozenset([LedgerLeg(asset_id=BTC, quantity=Decimal("-1"), account_chain_id=LEDGER_WALLET)]),
        )
