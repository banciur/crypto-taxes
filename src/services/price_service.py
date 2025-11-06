from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .price_sources import DeterministicRandomPriceSource, PriceSource
from .price_store import JsonlPriceStore, PriceStore


class PriceService:
    def __init__(
        self,
        source: PriceSource,
        store: PriceStore,
    ) -> None:
        self.source = source
        self.store = store

    def get_price(
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


def build_default_service() -> PriceService:
    source = DeterministicRandomPriceSource()
    store = JsonlPriceStore(root_dir=Path("data"))
    return PriceService(source=source, store=store)


__all__ = ["PriceService", "build_default_service"]
