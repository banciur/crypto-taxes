import logging
from datetime import datetime, timezone
from decimal import Decimal

from domain.ledger import AssetId
from domain.pricing import PriceProvider

from .price_sources import PriceSnapshotSource
from .price_store import PriceStore

logger = logging.getLogger(__name__)


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
    ) -> Decimal | None:
        ts = timestamp or datetime.now(timezone.utc)
        existing = self.store.read(base_id=base_id, quote_id=quote_id, timestamp=ts)
        if existing is not None:
            return existing.rate

        logger.info("Price cache miss, fetching %s->%s @ %s from source", base_id, quote_id, ts.isoformat())
        fetched = self.source.fetch_snapshot(base_id=base_id, quote_id=quote_id, timestamp=ts)
        if fetched is None:
            return None
        self.store.write(fetched)
        return fetched.rate
