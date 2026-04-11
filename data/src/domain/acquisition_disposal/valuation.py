from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ..ledger import AssetId
from ..pricing import PriceProvider
from .constants import BASE_CURRENCY_ASSET_ID
from .errors import AcquisitionDisposalProjectionError
from .pipeline_types import _ProjectedAssetGroup, _ProjectedEvent


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
    fee_prices = _value_fee_buckets(
        projected_event,
        non_fee_prices=non_fee_prices,
        timestamp=timestamp,
        price_provider=price_provider,
    )
    return non_fee_prices | fee_prices


def _value_non_fee_buckets(
    projected_event: _ProjectedEvent,
    *,
    timestamp: datetime,
    price_provider: PriceProvider,
) -> dict[AssetId, Decimal]:
    if not projected_event.non_fee_buckets:
        return {}

    direct_rates: dict[AssetId, Decimal] = {}
    unknown_buckets: list[_ProjectedAssetGroup] = []

    for bucket in projected_event.non_fee_buckets:
        direct_rate = _try_direct_rate(
            asset_id=bucket.asset_id,
            timestamp=timestamp,
            price_provider=price_provider,
        )
        if direct_rate is None:
            unknown_buckets.append(bucket)
        else:
            direct_rates[bucket.asset_id] = direct_rate

    if len(unknown_buckets) > 1:
        raise AcquisitionDisposalProjectionError(
            "More than one distinct non-fee asset is unpriceable in the same event."
        )

    if unknown_buckets:
        unknown_bucket = unknown_buckets[0]
        solved_rate = _solve_unknown_rate(
            projected_event,
            direct_rates=direct_rates,
            unknown_bucket=unknown_bucket,
        )
        return direct_rates | {unknown_bucket.asset_id: solved_rate}

    if projected_event.exact_base_currency is None:
        return direct_rates

    return _apply_exact_base_currency_balance(
        projected_event,
        direct_rates=direct_rates,
    )


def _value_fee_buckets(
    projected_event: _ProjectedEvent,
    *,
    non_fee_prices: dict[AssetId, Decimal],
    timestamp: datetime,
    price_provider: PriceProvider,
) -> dict[AssetId, Decimal]:
    fee_prices: dict[AssetId, Decimal] = {}

    for bucket in projected_event.fee_buckets:
        if bucket.asset_id in fee_prices:
            continue
        if bucket.asset_id in non_fee_prices:
            fee_prices[bucket.asset_id] = non_fee_prices[bucket.asset_id]
            continue

        direct_rate = _try_direct_rate(
            asset_id=bucket.asset_id,
            timestamp=timestamp,
            price_provider=price_provider,
        )
        if direct_rate is None:
            raise AcquisitionDisposalProjectionError(
                f"Fee asset appears only in fee legs and cannot be priced in EUR: asset={bucket.asset_id}."
            )
        fee_prices[bucket.asset_id] = direct_rate

    return fee_prices


def _apply_exact_base_currency_balance(
    projected_event: _ProjectedEvent,
    *,
    direct_rates: dict[AssetId, Decimal],
) -> dict[AssetId, Decimal]:
    exact_base_currency = projected_event.exact_base_currency
    if exact_base_currency is None:
        return direct_rates

    fixed_side = 1 if exact_base_currency > 0 else -1
    floating_buckets = [bucket for bucket in projected_event.non_fee_buckets if _bucket_side(bucket) == -fixed_side]
    if not floating_buckets:
        return direct_rates

    fixed_total = abs(exact_base_currency) + _side_total(
        projected_event.non_fee_buckets,
        rates=direct_rates,
        side=fixed_side,
    )
    floating_total = sum(
        (_direct_total(bucket, rate=direct_rates[bucket.asset_id]) for bucket in floating_buckets),
        start=Decimal(0),
    )
    if floating_total <= 0:
        raise AcquisitionDisposalProjectionError(
            "One-sided event relies on direct price service valuation and the price is unavailable."
        )

    balanced_rates = dict(direct_rates)
    remaining_total = fixed_total
    for bucket in floating_buckets[:-1]:
        scaled_total = fixed_total * _direct_total(bucket, rate=direct_rates[bucket.asset_id]) / floating_total
        remaining_total -= scaled_total
        balanced_rates[bucket.asset_id] = scaled_total / abs(_bucket_net_quantity(bucket))

    final_bucket = floating_buckets[-1]
    balanced_rates[final_bucket.asset_id] = remaining_total / abs(_bucket_net_quantity(final_bucket))
    return balanced_rates


def _solve_unknown_rate(
    projected_event: _ProjectedEvent,
    *,
    direct_rates: dict[AssetId, Decimal],
    unknown_bucket: _ProjectedAssetGroup,
) -> Decimal:
    exact_base_currency = projected_event.exact_base_currency or Decimal(0)
    known_acquisition_total = _side_total(projected_event.non_fee_buckets, rates=direct_rates, side=1)
    known_disposal_total = _side_total(projected_event.non_fee_buckets, rates=direct_rates, side=-1)

    if exact_base_currency > 0:
        known_acquisition_total += exact_base_currency
    elif exact_base_currency < 0:
        known_disposal_total += abs(exact_base_currency)

    if _bucket_side(unknown_bucket) > 0:
        opposite_total = known_disposal_total
        same_side_total = known_acquisition_total
    else:
        opposite_total = known_acquisition_total
        same_side_total = known_disposal_total

    if opposite_total <= 0:
        raise AcquisitionDisposalProjectionError(
            "One-sided event relies on direct price service valuation and the price is unavailable."
        )

    unknown_total = opposite_total - same_side_total
    if unknown_total < 0:
        raise AcquisitionDisposalProjectionError(
            f"Remainder solving would produce a negative value for asset={unknown_bucket.asset_id}."
        )

    return unknown_total / abs(_bucket_net_quantity(unknown_bucket))


def _side_total(
    buckets: tuple[_ProjectedAssetGroup, ...],
    *,
    rates: dict[AssetId, Decimal],
    side: int,
) -> Decimal:
    return sum(
        (
            _direct_total(bucket, rate=rates[bucket.asset_id])
            for bucket in buckets
            if _bucket_side(bucket) == side and bucket.asset_id in rates
        ),
        start=Decimal(0),
    )


def _direct_total(bucket: _ProjectedAssetGroup, *, rate: Decimal) -> Decimal:
    return rate * abs(_bucket_net_quantity(bucket))


def _bucket_side(bucket: _ProjectedAssetGroup) -> int:
    return 1 if _bucket_net_quantity(bucket) > 0 else -1


def _bucket_net_quantity(bucket: _ProjectedAssetGroup) -> Decimal:
    return sum((leg.quantity for leg in bucket.legs), start=Decimal(0))


def _try_direct_rate(
    *,
    asset_id: AssetId,
    timestamp: datetime,
    price_provider: PriceProvider,
) -> Decimal | None:
    try:
        return price_provider.rate(asset_id, BASE_CURRENCY_ASSET_ID, timestamp)
    except Exception:
        return None
