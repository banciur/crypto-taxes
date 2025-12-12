from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from services.price_service import PriceService
from services.price_store import JsonlPriceStore
from tests.helpers.random_price_service import DeterministicRandomPriceSource


def test_fetch_and_get_flow(tmp_path: Path) -> None:
    source = DeterministicRandomPriceSource(seed=123)
    store = JsonlPriceStore(root_dir=tmp_path)
    fixed_now = datetime(2025, 1, 1, 15, 30, tzinfo=timezone.utc)
    service = PriceService(
        source=source,
        store=store,
    )

    rate = service.rate("ETH", "EUR", timestamp=fixed_now)
    assert isinstance(rate, Decimal)

    stored_rate = service.rate("ETH", "EUR", timestamp=fixed_now)
    assert stored_rate == rate


def test_get_price_reuses_cached_snapshot(tmp_path: Path) -> None:
    source = DeterministicRandomPriceSource(seed=1)
    store = JsonlPriceStore(root_dir=tmp_path)
    base_ts = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    service = PriceService(
        source=source,
        store=store,
    )

    first_rate = service.rate("BTC", "USD", timestamp=base_ts)
    reused_rate = service.rate("BTC", "USD", timestamp=base_ts)
    assert reused_rate == first_rate

    later_ts = base_ts.replace(minute=base_ts.minute + 2)
    refreshed_rate = service.rate("BTC", "USD", timestamp=later_ts)
    assert refreshed_rate != first_rate
