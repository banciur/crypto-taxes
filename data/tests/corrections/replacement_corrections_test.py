from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from corrections.replacements import apply_replacement_corrections
from domain.correction import Replacement
from domain.ledger import AccountChainId, EventLocation, EventOrigin, LedgerEvent, LedgerEventId, LedgerLeg
from tests.constants import BTC, ETH, KRAKEN_WALLET, LEDGER_WALLET


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


def test_apply_replacement_corrections_replaces_raw_events_with_synthetic_event() -> None:
    replaced_first = _raw_event(
        location=EventLocation.ETHEREUM,
        external_id="0xsend",
        hour=10,
        quantity=Decimal("-0.1"),
        wallet_id=KRAKEN_WALLET,
    )
    replaced_second = _raw_event(
        location=EventLocation.COINBASE,
        external_id="cb-receive",
        hour=11,
        quantity=Decimal("0.09995"),
        wallet_id=LEDGER_WALLET,
    )
    kept = _raw_event(
        location=EventLocation.KRAKEN,
        external_id="kraken-keep",
        hour=12,
        quantity=Decimal("0.25"),
        wallet_id=KRAKEN_WALLET,
    )
    replacement = Replacement(
        timestamp=datetime(2024, 1, 1, 11, 30, tzinfo=timezone.utc),
        sources=[replaced_first.event_origin, replaced_second.event_origin],
        legs=[
            LedgerLeg(asset_id=BTC, quantity=Decimal("-0.1"), account_chain_id=KRAKEN_WALLET),
            LedgerLeg(asset_id=BTC, quantity=Decimal("0.09995"), account_chain_id=LEDGER_WALLET),
            LedgerLeg(asset_id=ETH, quantity=Decimal("-0.001"), account_chain_id=KRAKEN_WALLET, is_fee=True),
        ],
    )

    corrected = list(
        apply_replacement_corrections(
            raw_events=[replaced_first, kept, replaced_second],
            replacements=[replacement],
        )
    )

    assert len(corrected) == 2
    assert {event.event_origin.external_id for event in corrected} == {
        kept.event_origin.external_id,
        f"replacement:{replacement.id}",
    }
    replacement_event = next(
        event for event in corrected if event.event_origin.external_id == f"replacement:{replacement.id}"
    )
    assert replacement_event.timestamp == replacement.timestamp
    assert replacement_event.ingestion == "replacement_correction"
    assert replacement_event.legs == replacement.legs


def test_apply_replacement_corrections_keeps_replacement_payload_verbatim() -> None:
    replaced = _raw_event(
        location=EventLocation.ETHEREUM,
        external_id="0xsource",
        hour=10,
        quantity=Decimal("-0.1"),
        wallet_id=KRAKEN_WALLET,
    )
    replacement = Replacement(
        timestamp=datetime(2024, 1, 1, 10, 30, tzinfo=timezone.utc),
        sources=[replaced.event_origin],
        legs=[
            LedgerLeg(asset_id=ETH, quantity=Decimal("-0.5"), account_chain_id=KRAKEN_WALLET, is_fee=True),
            LedgerLeg(asset_id=BTC, quantity=Decimal("2"), account_chain_id=LEDGER_WALLET),
        ],
    )

    corrected = list(
        apply_replacement_corrections(
            raw_events=[replaced],
            replacements=[replacement],
        )
    )

    assert len(corrected) == 1
    assert corrected[0].legs == replacement.legs


def test_apply_replacement_corrections_preserves_raw_order_then_appends_replacements() -> None:
    kept = _raw_event(
        location=EventLocation.KRAKEN,
        external_id="kraken-keep",
        hour=12,
        quantity=Decimal("0.25"),
        wallet_id=KRAKEN_WALLET,
    )
    replaced = _raw_event(
        location=EventLocation.ETHEREUM,
        external_id="0xsource",
        hour=13,
        quantity=Decimal("-0.1"),
        wallet_id=KRAKEN_WALLET,
    )
    earlier_replacement = Replacement(
        timestamp=datetime(2024, 1, 1, 9, 30, tzinfo=timezone.utc),
        sources=[replaced.event_origin],
        legs=[LedgerLeg(asset_id=BTC, quantity=Decimal("1"), account_chain_id=LEDGER_WALLET)],
    )

    corrected = list(
        apply_replacement_corrections(
            raw_events=[kept, replaced],
            replacements=[earlier_replacement],
        )
    )

    assert [event.event_origin.external_id for event in corrected] == [
        kept.event_origin.external_id,
        f"replacement:{earlier_replacement.id}",
    ]
