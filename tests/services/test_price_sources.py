from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from services.price_sources import DeterministicRandomPriceSource, HybridPriceSource
from services.price_types import PriceQuote


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


class _StubPriceSnapshotSource:
    def __init__(self, *, rate: Decimal, source_name: str) -> None:
        self.rate = rate
        self.source_name = source_name
        self.calls: list[tuple[str, str, datetime]] = []

    def fetch_snapshot(self, base_id: str, quote_id: str, timestamp: datetime) -> PriceQuote:
        self.calls.append((base_id, quote_id, timestamp))
        return PriceQuote(
            timestamp=timestamp,
            base_id=base_id,
            quote_id=quote_id,
            rate=self.rate,
            source=self.source_name,
            valid_from=timestamp,
            valid_to=timestamp,
        )


def test_hybrid_source_routes_fiat_pairs() -> None:
    crypto = _StubPriceSnapshotSource(rate=Decimal("1"), source_name="crypto")
    fiat = _StubPriceSnapshotSource(rate=Decimal("2"), source_name="fiat")
    source = HybridPriceSource(crypto_source=crypto, fiat_source=fiat, fiat_currency_codes=("EUR", "PLN"))
    ts = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)

    quote = source.fetch_snapshot("eur", "pln", timestamp=ts)

    assert quote.rate == Decimal("2")
    assert fiat.calls == [("EUR", "PLN", ts)]
    assert crypto.calls == []


def test_hybrid_source_uses_crypto_for_non_fiat_pairs() -> None:
    crypto = _StubPriceSnapshotSource(rate=Decimal("3"), source_name="crypto")
    fiat = _StubPriceSnapshotSource(rate=Decimal("4"), source_name="fiat")
    source = HybridPriceSource(crypto_source=crypto, fiat_source=fiat, fiat_currency_codes=("EUR", "PLN"))
    ts = datetime(2025, 1, 1, 15, 0, tzinfo=timezone.utc)

    quote = source.fetch_snapshot("btc", "eur", timestamp=ts)

    assert quote.rate == Decimal("3")
    assert crypto.calls == [("BTC", "EUR", ts)]
    assert fiat.calls == []
