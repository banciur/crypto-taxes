import logging
from datetime import datetime, timezone
from decimal import Decimal

from config import ASSETS_PRICED_AS, ASSETS_PRICED_AS_NEGATED, NUMERAIRE_ASSET_ID, STABLE_ASSETS_BY_PEG
from domain.ledger import AssetId
from domain.pricing import PriceCache, PriceProvider

from .price_resolver import PriceResolver

logger = logging.getLogger(__name__)

_PEG_BY_STABLE: dict[AssetId, AssetId] = {
    stable: peg for peg, stables in STABLE_ASSETS_BY_PEG.items() for stable in stables
}

_PRICED_AS_BY_ASSET: dict[AssetId, AssetId] = {
    asset: priced_as for priced_as, assets in ASSETS_PRICED_AS.items() for asset in assets
}

_NEGATED_PRICED_AS_BY_ASSET: dict[AssetId, AssetId] = {
    asset: priced_as for priced_as, assets in ASSETS_PRICED_AS_NEGATED.items() for asset in assets
}


class PriceService(PriceProvider):
    """Resolves `base -> quote` rates through a single numeraire pivot.

    Resolution order for `rate(base, quote, ts)`:

    0. substitute each side that is priced as another asset (rETH2 -> ETH).
    1. `base == quote` -> `1` (short-circuits before any store/source lookup).
    2. a cached `base -> quote` edge (including manual entries) -> use it, no network.
    3. otherwise pivot: resolve `base -> numeraire` and `quote -> numeraire` and divide.

    Each leg `asset -> numeraire` resolves as: cached edge -> stable peg -> fetch through the
    resolver. A pegged stable is treated as one unit of its peg currency, so its leg is the peg
    currency's own leg (USDC -> USD -> 1; EURC -> EUR -> the EUR/USD rate). Only fetched *leg*
    edges are cached; the composed cross-rate is recomputed on every call, so later manual edges
    are picked up with nothing stale to invalidate.
    """

    def __init__(self, resolver: PriceResolver, cache: PriceCache) -> None:
        self.resolver = resolver
        self.cache = cache

    def rate(
        self,
        base_id: AssetId,
        quote_id: AssetId,
        timestamp: datetime | None = None,
    ) -> Decimal | None:
        ts = timestamp or datetime.now(timezone.utc)
        base, base_sign = _substitute(AssetId(base_id.upper()))
        quote, quote_sign = _substitute(AssetId(quote_id.upper()))
        sign = base_sign * quote_sign

        if base == quote:
            return Decimal(sign)

        direct = self.cache.read(base_id=base, quote_id=quote, timestamp=ts)
        if direct is not None:
            return None if direct.rate is None else direct.rate * sign

        base_leg = self._resolve_to_numeraire(base, ts)
        quote_leg = self._resolve_to_numeraire(quote, ts)
        if base_leg is None or quote_leg is None:
            return None
        return (base_leg / quote_leg) * sign

    def _resolve_to_numeraire(self, asset: AssetId, timestamp: datetime) -> Decimal | None:
        if asset == NUMERAIRE_ASSET_ID:
            return Decimal(1)

        cached = self.cache.read(base_id=asset, quote_id=NUMERAIRE_ASSET_ID, timestamp=timestamp)
        if cached is not None:
            return cached.rate

        peg_currency = _PEG_BY_STABLE.get(asset)
        if peg_currency is not None:
            # A pegged stable is worth one unit of its peg currency; resolve that to the numeraire.
            return self._resolve_to_numeraire(peg_currency, timestamp)

        logger.info(
            "Price cache miss, fetching %s->%s @ %s from source", asset, NUMERAIRE_ASSET_ID, timestamp.isoformat()
        )
        record = self.resolver.fetch_record(asset, NUMERAIRE_ASSET_ID, timestamp)
        self.cache.write(record)
        return record.rate


def _substitute(asset: AssetId) -> tuple[AssetId, int]:
    """Return the asset actually priced and the sign its EUR value carries.

    A negated priced-as asset (a debt/liability token) borrows its underlying's market rate with the
    sign flipped: holding one is owing the underlying, so its EUR value is negative.
    """
    negated = _NEGATED_PRICED_AS_BY_ASSET.get(asset)
    if negated is not None:
        return negated, -1
    return _PRICED_AS_BY_ASSET.get(asset, asset), 1
