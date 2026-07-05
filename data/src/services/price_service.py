import logging
from datetime import datetime, timezone
from decimal import Decimal

from domain.ledger import AssetId
from domain.pricing import PriceCache, PriceProvider

from .price_resolver import PriceResolver

logger = logging.getLogger(__name__)


class PriceService(PriceProvider):
    def __init__(
        self,
        resolver: PriceResolver,
        cache: PriceCache,
    ) -> None:
        self.resolver = resolver
        self.cache = cache

    def rate(
        self,
        base_id: AssetId,
        quote_id: AssetId,
        timestamp: datetime | None = None,
    ) -> Decimal | None:
        ts = timestamp or datetime.now(timezone.utc)
        base = AssetId(base_id.upper())
        quote = AssetId(quote_id.upper())

        existing = self.cache.read(base_id=base, quote_id=quote, timestamp=ts)
        if existing is not None:
            return existing.rate

        logger.info("Price cache miss, fetching %s->%s @ %s from source", base, quote, ts.isoformat())
        fetched = self.resolver.resolve(base_id=base, quote_id=quote, timestamp=ts)
        self.cache.write(fetched)
        return fetched.rate
