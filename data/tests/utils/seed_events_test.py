from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from domain.base_types import EventLocation
from importers.seed_events import DEFAULT_SEED_TIMESTAMP, load_seed_events


def test_load_seed_events_defaults(tmp_path: Path) -> None:
    csv_file = tmp_path / "seeds.csv"
    csv_file.write_text("asset_id,wallet_id,quantity\nETH,ledger,0.5\n")

    events = load_seed_events(csv_file)

    assert len(events) == 1
    event = events[0]
    assert event.event_type.value == "TRADE"
    assert event.timestamp == DEFAULT_SEED_TIMESTAMP
    assert event.origin.location == EventLocation.INTERNAL
    assert event.origin.external_id == "seed_csv_row:1"
    assert event.ingestion == "seed_csv"
    asset_leg, eur_leg = sorted(event.legs, key=lambda leg: leg.asset_id)
    assert asset_leg.asset_id == "ETH"
    assert asset_leg.quantity == Decimal("0.5")
    assert asset_leg.wallet_id == "ledger"
    assert eur_leg.asset_id == "EUR"
    assert eur_leg.quantity == Decimal("-0.0001")
    assert eur_leg.wallet_id == "ledger"


def test_load_seed_events_with_timestamp_and_cost(tmp_path: Path) -> None:
    csv_file = tmp_path / "seeds.csv"
    csv_file.write_text(
        "asset_id,wallet_id,quantity,timestamp,cost_total_eur\nBTC,kraken,0.25,2020-01-01T12:00:00,1.23\n"
    )

    events = load_seed_events(csv_file)
    event = events[0]

    assert event.timestamp == datetime(2020, 1, 1, 12, tzinfo=timezone.utc)
    assert event.origin.external_id == "seed_csv_row:1"
    assert event.ingestion == "seed_csv"
    asset_leg, eur_leg = sorted(event.legs, key=lambda leg: leg.asset_id)
    assert asset_leg.asset_id == "BTC"
    assert eur_leg.quantity == Decimal("-1.23")


def test_missing_seed_file_returns_empty(tmp_path: Path) -> None:
    csv_file = tmp_path / "missing.csv"
    assert load_seed_events(csv_file) == []
