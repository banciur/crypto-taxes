from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from db.price_cache import PriceCacheRepository, init_price_cache_db
from domain.ledger import AssetId
from domain.pricing import PriceRecord
from tests.constants import BTC, ETH, EUR, USD


def _price(base: AssetId, quote: AssetId, rate: str, timestamp: datetime, *, duration_minutes: int = 0) -> PriceRecord:
    valid_to = timestamp if duration_minutes == 0 else timestamp + timedelta(minutes=duration_minutes)
    return PriceRecord(
        base_id=base,
        quote_id=quote,
        rate=Decimal(rate),
        source="test",
        valid_from=timestamp,
        valid_to=valid_to,
        fetched_at=timestamp,
    )


def _store(tmp_path: Path) -> PriceCacheRepository:
    session = init_price_cache_db(db_path=tmp_path / "price_cache.db")
    return PriceCacheRepository(session)


def test_store_returns_snapshot_within_coverage_window(tmp_path: Path) -> None:
    store = _store(tmp_path)
    valid_from = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    base_id = BTC
    quote_id = EUR
    rate = "100.00"

    store.write(_price(base_id, quote_id, rate, valid_from, duration_minutes=59))

    result = store.read(base_id, quote_id, datetime(2025, 1, 1, 12, 45, tzinfo=timezone.utc))
    assert result is not None
    assert result.rate == Decimal(rate)


def test_store_returns_none_when_outside_coverage(tmp_path: Path) -> None:
    store = _store(tmp_path)
    valid_from = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    base_id = ETH
    quote_id = USD
    rate = "50.00"
    price = _price(base_id, quote_id, rate, valid_from, duration_minutes=10)
    store.write(price)

    result = store.read(base_id, quote_id, datetime(2025, 1, 1, 12, 30, tzinfo=timezone.utc))
    assert result is None


def test_store_prefers_higher_resolution_for_overlapping_windows(tmp_path: Path) -> None:
    store = _store(tmp_path)
    ts = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    later_ts = ts.replace(second=30)
    base_id = BTC
    quote_id = USD
    later_rate = "101.00"
    store.write(_price(base_id, quote_id, "100.00", ts, duration_minutes=60 * 12))
    store.write(_price(base_id, quote_id, later_rate, later_ts, duration_minutes=1))

    result = store.read(base_id, quote_id, later_ts)
    assert result is not None
    assert result.rate == Decimal(later_rate)


def test_store_records_negative_cache_rows(tmp_path: Path) -> None:
    store = _store(tmp_path)
    valid_from = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    base_id = BTC
    quote_id = EUR

    store.write(
        PriceRecord(
            base_id=base_id,
            quote_id=quote_id,
            rate=None,
            source="test",
            valid_from=valid_from,
            valid_to=valid_from + timedelta(minutes=1),
            fetched_at=valid_from,
        )
    )

    result = store.read(base_id, quote_id, valid_from)
    assert result is not None
    assert result.rate is None


def test_store_deduplicates_bucket_start(tmp_path: Path) -> None:
    store = _store(tmp_path)
    timestamp = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    base_id = ETH
    quote_id = EUR
    replacement_rate = "125.00"

    store.write(_price(base_id, quote_id, "100.00", timestamp, duration_minutes=60))
    store.write(_price(base_id, quote_id, replacement_rate, timestamp, duration_minutes=60))

    result = store.read(base_id, quote_id, timestamp)
    assert result is not None
    assert result.rate == Decimal(replacement_rate)
