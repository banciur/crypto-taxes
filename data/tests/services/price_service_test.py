from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from domain.ledger import AssetId
from domain.pricing import RequiredPriceUnavailableError
from services.price_service import PriceService
from services.price_store import JsonlPriceStore
from services.price_types import PriceQuote
from tests.constants import BTC, ETH, EUR, USD
from tests.helpers.random_price_service import DeterministicRandomPriceSource


def test_fetch_and_get_flow(tmp_path: Path) -> None:
    source = DeterministicRandomPriceSource(seed=123)
    store = JsonlPriceStore(root_dir=tmp_path)
    fixed_now = datetime(2025, 1, 1, 15, 30, tzinfo=timezone.utc)
    service = PriceService(
        source=source,
        store=store,
    )

    rate = service.rate(ETH, EUR, timestamp=fixed_now)
    assert isinstance(rate, Decimal)

    stored_rate = service.rate(ETH, EUR, timestamp=fixed_now)
    assert stored_rate == rate


def test_get_price_reuses_cached_snapshot(tmp_path: Path) -> None:
    source = DeterministicRandomPriceSource(seed=1)
    store = JsonlPriceStore(root_dir=tmp_path)
    base_ts = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    service = PriceService(
        source=source,
        store=store,
    )

    first_rate = service.rate(BTC, USD, timestamp=base_ts)
    reused_rate = service.rate(BTC, USD, timestamp=base_ts)
    assert reused_rate == first_rate

    later_ts = base_ts.replace(minute=base_ts.minute + 2)
    refreshed_rate = service.rate(BTC, USD, timestamp=later_ts)
    assert refreshed_rate != first_rate


class _FailingPriceSnapshotSource:
    def fetch_snapshot(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> PriceQuote:
        _ = (base_id, quote_id, timestamp)
        raise LookupError("missing price")


def test_anchor_asset_requires_direct_eur_price(tmp_path: Path) -> None:
    store = JsonlPriceStore(root_dir=tmp_path)
    fixed_now = datetime(2025, 1, 1, 15, 30, tzinfo=timezone.utc)
    service = PriceService(
        source=_FailingPriceSnapshotSource(),
        store=store,
    )

    with pytest.raises(RequiredPriceUnavailableError, match="Valuation anchor must have a direct EUR price"):
        service.rate(USD, EUR, timestamp=fixed_now)
