from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from domain.correction import SeedEvent
from domain.ledger import EventLocation, EventType, LedgerLeg
from importers.seed_events import (
    DEFAULT_SEED_TIMESTAMP,
    SEED_CSV_INGESTION,
    ledger_events_from_seed_events,
    load_seed_events,
)
from tests.constants import BTC, KRAKEN_WALLET


def test_load_seed_events_defaults(tmp_path: Path) -> None:
    csv_file = tmp_path / "seeds.csv"
    csv_file.write_text("asset_id,wallet_id,quantity\nETH,ledger,0.5\n")

    events = load_seed_events(csv_file)

    assert len(events) == 1
    event = events[0]
    assert event.timestamp == DEFAULT_SEED_TIMESTAMP
    assert event.price_per_token == Decimal("0")

    assert len(event.legs) == 1
    (leg,) = event.legs
    assert leg.asset_id == "ETH"
    assert leg.quantity == Decimal("0.5")
    assert leg.wallet_id == "ledger"
    assert leg.is_fee is False


def test_load_seed_events_with_timestamp_and_price_per_token(tmp_path: Path) -> None:
    csv_file = tmp_path / "seeds.csv"
    timestamp = datetime(2020, 1, 1, 12, tzinfo=timezone.utc)
    price_per_token = Decimal("1.23")
    csv_file.write_text(
        f"asset_id,wallet_id,quantity,timestamp,price_per_token\nBTC,kraken,0.25,{timestamp.isoformat().replace('+00:00', 'Z')},{price_per_token}\n"
    )

    events = load_seed_events(csv_file)
    event = events[0]

    assert event.timestamp == timestamp
    assert event.price_per_token == price_per_token
    assert len(event.legs) == 1
    (leg,) = event.legs
    assert leg.asset_id == "BTC"
    assert leg.quantity == Decimal("0.25")
    assert leg.wallet_id == "kraken"


def test_missing_seed_file_returns_empty(tmp_path: Path) -> None:
    csv_file = tmp_path / "missing.csv"
    assert load_seed_events(csv_file) == []


def test_ledger_events_from_seed_events() -> None:
    timestamp = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    quantity = Decimal("0.5")
    price_per_token = Decimal("123.45")

    seed_event = SeedEvent(
        timestamp=timestamp,
        price_per_token=price_per_token,
        legs=[LedgerLeg(asset_id=BTC, quantity=quantity, wallet_id=KRAKEN_WALLET, is_fee=False)],
    )

    ledger_events = ledger_events_from_seed_events([seed_event])

    assert len(ledger_events) == 1
    (event,) = ledger_events
    assert event.timestamp == timestamp
    assert event.ingestion == SEED_CSV_INGESTION
    assert event.event_type == EventType.REWARD
    assert event.origin.location == EventLocation.INTERNAL
    assert event.origin.external_id == f"seed:{seed_event.id}"
    assert len(event.legs) == 1
    (leg,) = event.legs
    assert leg.asset_id == BTC
    assert leg.quantity == quantity
    assert leg.wallet_id == KRAKEN_WALLET
    assert leg.is_fee is False
