from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from domain.pricing import PriceProvider

from .price_sources import PriceSnapshotSource
from .price_store import PriceStore


class PriceService(PriceProvider):
    def __init__(
        self,
        source: PriceSnapshotSource,
        store: PriceStore,
    ) -> None:
        self.source = source
        self.store = store

    def rate(
        self,
        base_id: str,
        quote_id: str,
        timestamp: datetime | None = None,
    ) -> Decimal:
        ts = timestamp or datetime.now(timezone.utc)
        existing = self.store.read(base_id=base_id, quote_id=quote_id, timestamp=ts)
        if existing is not None:
            return existing.rate

        fetched = self.source.fetch_snapshot(base_id=base_id, quote_id=quote_id, timestamp=ts)
        self.store.write(fetched)
        return fetched.rate
