from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from services.price_sources import DeterministicRandomPriceSource


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
