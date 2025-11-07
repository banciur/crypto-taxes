from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import cast

import pytest

from services.coindesk_client import CoinDeskClient, SpotInstrumentOHLC
from services.price_sources import CoinDeskPriceSource, DeterministicRandomPriceSource


class _StubCoinDeskClient:
    def __init__(self, entries: list[SpotInstrumentOHLC]) -> None:
        self.entries = entries
        self.captured_minutes_params: dict[str, object] | None = None
        self.captured_hours_params: dict[str, object] | None = None

    def get_spot_historical_minutes(self, **params: object) -> list[SpotInstrumentOHLC]:
        self.captured_minutes_params = params
        return self.entries

    def get_spot_historical_hours(self, **params: object) -> list[SpotInstrumentOHLC]:
        self.captured_hours_params = params
        return self.entries


def test_deterministic_source_returns_same_rate_for_same_inputs() -> None:
    source = DeterministicRandomPriceSource(seed=42)
    timestamp = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)

    first = source.fetch_snapshot("BTC", "EUR", timestamp=timestamp)
    second = source.fetch_snapshot("btc", "eur", timestamp=timestamp)

    assert first.rate == second.rate
    assert first.timestamp == timestamp
    assert first.source == source.source_name
    assert first.valid_from == timestamp
    assert first.valid_to == timestamp


def test_deterministic_source_varies_with_timestamp() -> None:
    source = DeterministicRandomPriceSource(seed=42)
    ts_a = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    ts_b = datetime(2025, 1, 1, 12, 1, tzinfo=timezone.utc)

    first = source.fetch_snapshot("ETH", "USD", timestamp=ts_a)
    second = source.fetch_snapshot("ETH", "USD", timestamp=ts_b)

    assert first.rate != second.rate


def test_deterministic_source_validates_price_bounds() -> None:
    with pytest.raises(ValueError):
        DeterministicRandomPriceSource(min_price=Decimal("0"), max_price=Decimal("10"))


def test_coindesk_price_source_transforms_hour_bucket_into_quote() -> None:
    bucket_start = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    entry = SpotInstrumentOHLC(
        timestamp=bucket_start,
        market="coinbase",
        instrument="BTCUSD",
        mapped_instrument="BTC-USD",
        base_asset="BTC",
        quote_asset="USD",
        open=Decimal("42000"),
        high=Decimal("42100"),
        low=Decimal("41900"),
        close=Decimal("42050.12"),
        volume=Decimal("10"),
        quote_volume=Decimal("420501.2"),
    )
    client = _StubCoinDeskClient([entry])

    source = CoinDeskPriceSource(client=cast(CoinDeskClient, client), market="coinbase")
    quote = source.fetch_snapshot("btc", "usd", timestamp=bucket_start)

    assert quote.rate == Decimal("42050.12")
    assert quote.valid_from == bucket_start
    assert quote.valid_to == bucket_start + timedelta(minutes=60)
    assert client.captured_hours_params is not None
    assert client.captured_minutes_params is None
    assert client.captured_hours_params["instrument"] == "BTC-USD"
    assert client.captured_hours_params["aggregate"] == 1


def test_coindesk_price_source_supports_minute_buckets() -> None:
    bucket_start = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    entry = SpotInstrumentOHLC(
        timestamp=bucket_start,
        market="coinbase",
        instrument="BTCUSD",
        mapped_instrument="BTC-USD",
        base_asset="BTC",
        quote_asset="USD",
        open=Decimal("42000"),
        high=Decimal("42100"),
        low=Decimal("41900"),
        close=Decimal("42050.12"),
        volume=Decimal("10"),
        quote_volume=Decimal("420501.2"),
    )
    client = _StubCoinDeskClient([entry])

    source = CoinDeskPriceSource(client=cast(CoinDeskClient, client), market="coinbase", aggregate_minutes=15)
    quote = source.fetch_snapshot("btc", "usd", timestamp=bucket_start)

    assert quote.valid_to == bucket_start + timedelta(minutes=15)
    assert client.captured_minutes_params is not None
    assert client.captured_minutes_params["aggregate"] == 15
    assert client.captured_hours_params is None


def test_coindesk_price_source_rejects_unsupported_bucket_lengths() -> None:
    client = cast(CoinDeskClient, _StubCoinDeskClient([]))
    with pytest.raises(ValueError):
        CoinDeskPriceSource(client=client, market="coinbase", aggregate_minutes=45)
