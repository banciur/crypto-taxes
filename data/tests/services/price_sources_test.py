from datetime import datetime, timezone
from decimal import Decimal

import pytest

from domain.ledger import AssetId
from domain.pricing import PriceRecord
from services.price_resolver import PriceResolver
from tests.constants import BTC, ETH, EUR, USD
from tests.helpers.random_price_service import DeterministicRandomPriceSource
from tests.services.constants import BTC_LOWER, EUR_LOWER, USD_LOWER


def test_deterministic_source_returns_same_rate_for_same_inputs() -> None:
    source = DeterministicRandomPriceSource(seed=42)
    timestamp = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)

    base_id = BTC
    quote_id = EUR
    first = source.fetch_record(base_id, quote_id, timestamp=timestamp)
    second = source.fetch_record(BTC_LOWER, EUR_LOWER, timestamp=timestamp)

    assert first.rate == second.rate
    assert first.source == source.source_name
    assert first.valid_from == timestamp
    assert first.valid_to == timestamp
    assert first.fetched_at == timestamp


def test_deterministic_source_varies_with_timestamp() -> None:
    source = DeterministicRandomPriceSource(seed=42)
    ts_a = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    ts_b = datetime(2025, 1, 1, 12, 1, tzinfo=timezone.utc)

    base_id = ETH
    quote_id = USD
    first = source.fetch_record(base_id, quote_id, timestamp=ts_a)
    second = source.fetch_record(base_id, quote_id, timestamp=ts_b)

    assert first.rate != second.rate


def test_deterministic_source_validates_price_bounds() -> None:
    with pytest.raises(ValueError):
        DeterministicRandomPriceSource(min_price=Decimal(0), max_price=Decimal("10"))


class _StubPriceSource:
    def __init__(self, *, rate: Decimal, source_name: str) -> None:
        self.rate = rate
        self.source_name = source_name
        self.calls: list[tuple[AssetId, AssetId, datetime]] = []

    def fetch_record(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> PriceRecord:
        self.calls.append((base_id, quote_id, timestamp))
        return PriceRecord(
            base_id=base_id,
            quote_id=quote_id,
            rate=self.rate,
            source=self.source_name,
            valid_from=timestamp,
            valid_to=timestamp,
            fetched_at=timestamp,
        )


def test_resolver_routes_fiat_pairs() -> None:
    crypto = _StubPriceSource(rate=Decimal("1"), source_name="crypto")
    fiat = _StubPriceSource(rate=Decimal("2"), source_name="fiat")
    resolver = PriceResolver(crypto_source=crypto, fiat_source=fiat, fiat_currency_codes=("EUR", "USD"))
    ts = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)

    quote = resolver.resolve(EUR_LOWER, USD_LOWER, timestamp=ts)

    assert quote is not None
    assert quote.rate == Decimal("2")
    assert fiat.calls == [(EUR, USD, ts)]
    assert crypto.calls == []


def test_resolver_uses_crypto_for_non_fiat_pairs() -> None:
    crypto = _StubPriceSource(rate=Decimal("3"), source_name="crypto")
    fiat = _StubPriceSource(rate=Decimal("4"), source_name="fiat")
    resolver = PriceResolver(crypto_source=crypto, fiat_source=fiat, fiat_currency_codes=("EUR", "USD"))
    ts = datetime(2025, 1, 1, 15, 0, tzinfo=timezone.utc)

    quote = resolver.resolve(BTC_LOWER, EUR_LOWER, timestamp=ts)

    assert quote is not None
    assert quote.rate == Decimal("3")
    assert crypto.calls == [(BTC, EUR, ts)]
    assert fiat.calls == []
