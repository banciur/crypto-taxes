from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from services.price_store import JsonlPriceStore
from services.price_types import PriceQuote


def _quote(base: str, quote: str, rate: str, timestamp: datetime, *, duration_minutes: int = 0) -> PriceQuote:
    valid_to = timestamp if duration_minutes == 0 else timestamp + timedelta(minutes=duration_minutes)
    return PriceQuote(
        timestamp=timestamp,
        base_id=base,
        quote_id=quote,
        rate=Decimal(rate),
        source="test",
        valid_from=timestamp,
        valid_to=valid_to,
    )


def test_store_returns_snapshot_within_coverage_window(tmp_path: Path) -> None:
    store = JsonlPriceStore(root_dir=tmp_path)
    valid_from = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    quote = _quote("BTC", "EUR", "100.00", valid_from, duration_minutes=59)

    store.write(quote)

    result = store.read("BTC", "EUR", datetime(2025, 1, 1, 12, 45, tzinfo=timezone.utc))
    assert result is not None
    assert result.rate == Decimal("100.00")


def test_store_returns_none_when_outside_coverage(tmp_path: Path) -> None:
    store = JsonlPriceStore(root_dir=tmp_path)
    valid_from = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    quote = _quote("ETH", "USD", "50.00", valid_from, duration_minutes=10)
    store.write(quote)

    result = store.read("ETH", "USD", datetime(2025, 1, 1, 12, 30, tzinfo=timezone.utc))
    assert result is None


def test_store_prefers_higher_resolution_for_overlapping_windows(tmp_path: Path) -> None:
    store = JsonlPriceStore(root_dir=tmp_path)
    ts = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    later_ts = ts.replace(second=30)
    store.write(
        _quote("BTC", "USD", "100.00", ts, duration_minutes=60 * 12),
    )
    store.write(
        _quote("BTC", "USD", "101.00", later_ts),
    )

    result = store.read("BTC", "USD", later_ts)
    assert result is not None
    assert result.rate == Decimal("101.00")
