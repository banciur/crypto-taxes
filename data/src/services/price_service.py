from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from domain.acquisition_disposal.constants import BASE_CURRENCY_ASSET_ID, is_valuation_anchor
from domain.ledger import AssetId
from domain.pricing import PriceProvider, RequiredPriceUnavailableError

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
        base_id: AssetId,
        quote_id: AssetId,
        timestamp: datetime | None = None,
    ) -> Decimal:
        ts = timestamp or datetime.now(timezone.utc)
        existing = self.store.read(base_id=base_id, quote_id=quote_id, timestamp=ts)
        if existing is not None:
            return existing.rate

        try:
            fetched = self.source.fetch_snapshot(base_id=base_id, quote_id=quote_id, timestamp=ts)
        except Exception as exc:
            if quote_id == BASE_CURRENCY_ASSET_ID and is_valuation_anchor(base_id):
                raise RequiredPriceUnavailableError(
                    f"Valuation anchor must have a direct EUR price: asset={base_id}"
                ) from exc
            raise
        self.store.write(fetched)
        return fetched.rate
