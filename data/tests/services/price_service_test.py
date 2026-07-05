from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from db.price_cache import PriceCacheRepository, init_price_cache_db
from domain.ledger import AssetId
from domain.pricing import PriceRecord, PriceSource
from services.price_resolver import PriceResolver
from services.price_service import PriceService
from tests.constants import BTC, ETH, EUR, USD


def _store(tmp_path: Path) -> PriceCacheRepository:
    session = init_price_cache_db(db_path=tmp_path / "price_cache.db")
    return PriceCacheRepository(session)


def _service(source: PriceSource, store: PriceCacheRepository) -> PriceService:
    resolver = PriceResolver(crypto_source=source, fiat_source=source)
    return PriceService(resolver=resolver, cache=store)


class _FixedPriceSource:
    def __init__(self, rate: Decimal) -> None:
        self.rate = rate
        self.calls = 0

    def fetch_record(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> PriceRecord:
        self.calls += 1
        return PriceRecord(
            base_id=base_id,
            quote_id=quote_id,
            rate=self.rate,
            source="test",
            valid_from=timestamp,
            valid_to=timestamp + timedelta(minutes=1),
            fetched_at=timestamp,
        )


def test_fetch_and_get_flow(tmp_path: Path) -> None:
    expected_rate = Decimal("123.45")
    source = _FixedPriceSource(expected_rate)
    store = _store(tmp_path)
    fixed_now = datetime(2025, 1, 1, 15, 30, tzinfo=timezone.utc)
    service = _service(source, store)

    rate = service.rate(ETH, EUR, timestamp=fixed_now)
    assert rate == expected_rate

    stored_rate = service.rate(ETH, EUR, timestamp=fixed_now)
    assert stored_rate == rate
    assert source.calls == 1


def test_get_price_reuses_cached_snapshot(tmp_path: Path) -> None:
    expected_rate = Decimal("456.78")
    source = _FixedPriceSource(expected_rate)
    store = _store(tmp_path)
    base_ts = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    service = _service(source, store)

    first_rate = service.rate(BTC, USD, timestamp=base_ts)
    reused_rate = service.rate(BTC, USD, timestamp=base_ts)
    assert reused_rate == first_rate
    assert source.calls == 1

    later_ts = base_ts.replace(minute=base_ts.minute + 2)
    refreshed_rate = service.rate(BTC, USD, timestamp=later_ts)
    assert refreshed_rate == first_rate
    assert source.calls == 2


class _UnpriceablePriceSource:
    def __init__(self, *, source_name: str = "unpriceable") -> None:
        self.source_name = source_name
        self.calls = 0

    def fetch_record(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> PriceRecord:
        self.calls += 1
        return PriceRecord(
            base_id=base_id,
            quote_id=quote_id,
            rate=None,
            source=self.source_name,
            valid_from=timestamp,
            valid_to=timestamp + timedelta(microseconds=1),
            fetched_at=timestamp,
        )


def test_unpriceable_pair_returns_none(tmp_path: Path) -> None:
    source = _UnpriceablePriceSource()
    store = _store(tmp_path)
    fixed_now = datetime(2025, 1, 1, 15, 30, tzinfo=timezone.utc)
    service = _service(source, store)

    assert service.rate(USD, EUR, timestamp=fixed_now) is None
    assert service.rate(USD, EUR, timestamp=fixed_now) is None
    assert source.calls == 1


def test_unpriceable_pair_records_routed_source_name(tmp_path: Path) -> None:
    crypto_source = _UnpriceablePriceSource(source_name="crypto-source")
    fiat_source = _UnpriceablePriceSource(source_name="fiat-source")
    store = _store(tmp_path)
    fixed_now = datetime(2025, 1, 1, 15, 30, tzinfo=timezone.utc)
    resolver = PriceResolver(crypto_source=crypto_source, fiat_source=fiat_source, fiat_currency_codes=("EUR", "USD"))
    service = PriceService(resolver=resolver, cache=store)

    assert service.rate(USD, EUR, timestamp=fixed_now) is None

    cached = store.read(USD, EUR, fixed_now)
    assert cached is not None
    assert cached.source == "fiat-source"


class _RaisingPriceSource:
    def fetch_record(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> PriceRecord:
        _ = base_id, quote_id, timestamp
        raise RuntimeError("backend down")


def test_operational_error_from_source_propagates(tmp_path: Path) -> None:
    store = _store(tmp_path)
    fixed_now = datetime(2025, 1, 1, 15, 30, tzinfo=timezone.utc)
    service = _service(_RaisingPriceSource(), store)

    with pytest.raises(RuntimeError, match="backend down"):
        service.rate(USD, EUR, timestamp=fixed_now)

    assert store.read(USD, EUR, fixed_now) is None
