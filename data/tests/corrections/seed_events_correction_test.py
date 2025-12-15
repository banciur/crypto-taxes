from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from corrections.seed_events import apply_seed_event_corrections
from domain.correction import SeedEvent
from domain.ledger import EventLocation, EventOrigin, EventType, LedgerEvent, LedgerEventId, LedgerLeg
from tests.constants import BTC, KRAKEN_WALLET


def test_apply_seed_event_corrections_merges_and_sorts() -> None:
    seed_timestamp = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    seed_quantity = Decimal("0.5")
    seed_event = SeedEvent(
        timestamp=seed_timestamp,
        legs=[LedgerLeg(asset_id=BTC, quantity=seed_quantity, wallet_id=KRAKEN_WALLET, is_fee=False)],
    )

    raw_timestamp = datetime(2024, 1, 2, 12, 0, tzinfo=timezone.utc)
    raw_quantity = Decimal("0.1")
    raw_event_id = LedgerEventId(uuid4())
    raw_event = LedgerEvent(
        id=raw_event_id,
        timestamp=raw_timestamp,
        origin=EventOrigin(location=EventLocation.KRAKEN, external_id="raw-ext"),
        ingestion="raw_ingestion",
        event_type=EventType.TRADE,
        legs=[LedgerLeg(asset_id=BTC, quantity=raw_quantity, wallet_id=KRAKEN_WALLET, is_fee=False)],
    )

    corrected = apply_seed_event_corrections(raw_events=[raw_event], seed_events=[seed_event])

    assert len(corrected) == 2
    assert corrected[0].timestamp == seed_timestamp
    assert corrected[1].id == raw_event_id
    assert {event.origin.external_id for event in corrected} == {"raw-ext", f"seed:{seed_event.id}"}
