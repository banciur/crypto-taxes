# This file is completely vibed and I didn't read it.
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from accounts import KRAKEN_ACCOUNT_ID
from corrections.ingestion import apply_ingestion_corrections
from corrections.validation import CorrectionValidationError
from domain.correction import Replacement, SeedEvent, Spam
from domain.ledger import AccountChainId, EventLocation, EventOrigin, LedgerEvent, LedgerEventId, LedgerLeg
from tests.constants import BTC, ETH, LEDGER_WALLET


def _raw_event(
    *,
    location: EventLocation,
    external_id: str,
    hour: int,
    quantity: Decimal,
    wallet_id: AccountChainId,
) -> LedgerEvent:
    return LedgerEvent(
        id=LedgerEventId(uuid4()),
        timestamp=datetime(2024, 1, 1, hour, 0, tzinfo=timezone.utc),
        event_origin=EventOrigin(location=location, external_id=external_id),
        ingestion="raw_ingestion",
        legs=[LedgerLeg(asset_id=BTC, quantity=quantity, account_chain_id=wallet_id, is_fee=False)],
    )


def test_apply_ingestion_corrections_applies_spam_replacement_seed_and_final_sort() -> None:
    spammed_raw = _raw_event(
        location=EventLocation.ARBITRUM,
        external_id="0xspam",
        hour=2,
        quantity=Decimal("1"),
        wallet_id=KRAKEN_ACCOUNT_ID,
    )
    replaced_first = _raw_event(
        location=EventLocation.ETHEREUM,
        external_id="0xsend",
        hour=3,
        quantity=Decimal("-0.1"),
        wallet_id=KRAKEN_ACCOUNT_ID,
    )
    replaced_second = _raw_event(
        location=EventLocation.COINBASE,
        external_id="cb-receive",
        hour=4,
        quantity=Decimal("0.09995"),
        wallet_id=LEDGER_WALLET,
    )
    kept_raw = _raw_event(
        location=EventLocation.KRAKEN,
        external_id="kraken-keep",
        hour=5,
        quantity=Decimal("0.25"),
        wallet_id=KRAKEN_ACCOUNT_ID,
    )
    replacement = Replacement(
        timestamp=datetime(2024, 1, 1, 4, 30, tzinfo=timezone.utc),
        sources=[replaced_first.event_origin, replaced_second.event_origin],
        legs=[
            LedgerLeg(asset_id=BTC, quantity=Decimal("-0.1"), account_chain_id=KRAKEN_ACCOUNT_ID),
            LedgerLeg(asset_id=BTC, quantity=Decimal("0.09995"), account_chain_id=LEDGER_WALLET),
            LedgerLeg(asset_id=ETH, quantity=Decimal("-0.001"), account_chain_id=KRAKEN_ACCOUNT_ID, is_fee=True),
        ],
    )
    seed_event = SeedEvent(
        timestamp=datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        legs=[LedgerLeg(asset_id=BTC, quantity=Decimal("0.5"), account_chain_id=LEDGER_WALLET)],
    )

    corrected = apply_ingestion_corrections(
        raw_events=[spammed_raw, kept_raw, replaced_first, replaced_second],
        spam_markers=[Spam(event_origin=spammed_raw.event_origin)],
        replacements=[replacement],
        seed_events=[seed_event],
    )

    assert [event.event_origin.external_id for event in corrected] == [
        f"seed:{seed_event.id}",
        f"replacement:{replacement.id}",
        kept_raw.event_origin.external_id,
    ]


def test_apply_ingestion_corrections_raises_on_invalid_correction_overlap() -> None:
    raw_event = _raw_event(
        location=EventLocation.ETHEREUM,
        external_id="0xshared",
        hour=3,
        quantity=Decimal("-0.1"),
        wallet_id=KRAKEN_ACCOUNT_ID,
    )
    replacement = Replacement(
        timestamp=datetime(2024, 1, 1, 4, 30, tzinfo=timezone.utc),
        sources=[raw_event.event_origin],
        legs=[LedgerLeg(asset_id=BTC, quantity=Decimal("1"), account_chain_id=LEDGER_WALLET)],
    )

    with pytest.raises(
        CorrectionValidationError,
        match="Raw event cannot be both spam and replacement source: ETHEREUM/0xshared",
    ):
        apply_ingestion_corrections(
            raw_events=[raw_event],
            spam_markers=[Spam(event_origin=raw_event.event_origin)],
            replacements=[replacement],
            seed_events=[],
        )
