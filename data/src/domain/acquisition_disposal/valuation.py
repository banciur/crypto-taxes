from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ..ledger import AssetId
from ..pricing import PriceProvider
from .constants import BASE_CURRENCY_ASSET_ID
from .pipeline_types import _ProjectedEvent


def value_projected_event(
    projected_event: _ProjectedEvent,
    *,
    timestamp: datetime,
    price_provider: PriceProvider,
) -> dict[AssetId, Decimal]:
    non_fee_prices = _value_non_fee_buckets(
        projected_event,
        timestamp=timestamp,
        price_provider=price_provider,
    )
    fee_prices = {
        bucket.asset_id: price_provider.rate(bucket.asset_id, BASE_CURRENCY_ASSET_ID, timestamp)
        for bucket in projected_event.fee_buckets
        if bucket.asset_id not in non_fee_prices
    }
    return non_fee_prices | fee_prices


def _value_non_fee_buckets(
    projected_event: _ProjectedEvent,
    *,
    timestamp: datetime,
    price_provider: PriceProvider,
) -> dict[AssetId, Decimal]:
    if projected_event.exact_base_currency is not None and len(projected_event.non_fee_buckets) == 1:
        (bucket,) = projected_event.non_fee_buckets
        quantity = abs(sum((leg.quantity for leg in bucket.legs), start=Decimal(0)))
        return {bucket.asset_id: abs(projected_event.exact_base_currency) / quantity}

    return {
        bucket.asset_id: price_provider.rate(bucket.asset_id, BASE_CURRENCY_ASSET_ID, timestamp)
        for bucket in projected_event.non_fee_buckets
    }
