from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from domain.ledger import AssetId
from services.price_store import JsonlPriceStore
from services.price_types import PriceQuote
from tests.constants import BTC, ETH, EUR, USD


def _quote(base: AssetId, quote: AssetId, rate: str, timestamp: datetime, *, duration_minutes: int = 0) -> PriceQuote:
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
    base_id = BTC
    quote_id = EUR

    store.write(_quote(base_id, quote_id, "100.00", valid_from, duration_minutes=59))

    result = store.read(base_id, quote_id, datetime(2025, 1, 1, 12, 45, tzinfo=timezone.utc))
    assert result is not None
    assert result.rate == Decimal("100.00")


def test_store_returns_none_when_outside_coverage(tmp_path: Path) -> None:
    store = JsonlPriceStore(root_dir=tmp_path)
    valid_from = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    base_id = ETH
    quote_id = USD
    quote = _quote(base_id, quote_id, "50.00", valid_from, duration_minutes=10)
    store.write(quote)

    result = store.read(base_id, quote_id, datetime(2025, 1, 1, 12, 30, tzinfo=timezone.utc))
    assert result is None


def test_store_prefers_higher_resolution_for_overlapping_windows(tmp_path: Path) -> None:
    store = JsonlPriceStore(root_dir=tmp_path)
    ts = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    later_ts = ts.replace(second=30)
    base_id = BTC
    quote_id = USD
    store.write(
        _quote(base_id, quote_id, "100.00", ts, duration_minutes=60 * 12),
    )
    store.write(
        _quote(base_id, quote_id, "101.00", later_ts),
    )

    result = store.read(base_id, quote_id, later_ts)
    assert result is not None
    assert result.rate == Decimal("101.00")
