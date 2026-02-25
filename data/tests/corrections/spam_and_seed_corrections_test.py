from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from corrections.seed_events import apply_seed_event_corrections
from corrections.spam import apply_spam_corrections
from domain.correction import SeedEvent, Spam
from domain.ledger import EventLocation, EventOrigin, LedgerEvent, LedgerEventId, LedgerLeg
from tests.constants import BTC, KRAKEN_WALLET


def _raw_event(*, external_id: str, hour: int) -> LedgerEvent:
    return LedgerEvent(
        id=LedgerEventId(uuid4()),
        timestamp=datetime(2024, 1, 1, hour, 0, tzinfo=timezone.utc),
        origin=EventOrigin(location=EventLocation.ARBITRUM, external_id=external_id),
        ingestion="moralis",
        legs=[LedgerLeg(asset_id=BTC, quantity=Decimal("1"), account_chain_id=KRAKEN_WALLET, is_fee=False)],
    )


def test_spam_filter_runs_before_seed_event_merge() -> None:
    spammed_raw = _raw_event(external_id="0xspam", hour=2)
    kept_raw = _raw_event(external_id="0xkeep", hour=3)
    seed_event = SeedEvent(
        timestamp=datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        price_per_token=Decimal("0"),
        legs=[LedgerLeg(asset_id=BTC, quantity=Decimal("0.5"), account_chain_id=KRAKEN_WALLET, is_fee=False)],
    )

    filtered = list(
        apply_spam_corrections(raw_events=[spammed_raw, kept_raw], spam_markers=[Spam(event_origin=spammed_raw.origin)])
    )
    corrected = apply_seed_event_corrections(raw_events=filtered, seed_events=[seed_event])

    assert {event.origin.external_id for event in corrected} == {kept_raw.origin.external_id, f"seed:{seed_event.id}"}
    assert corrected[0].origin.external_id == f"seed:{seed_event.id}"
