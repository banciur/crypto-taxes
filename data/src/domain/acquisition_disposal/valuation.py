from __future__ import annotations

from decimal import Decimal

from ..ledger import AssetId
from ..pricing import PriceProvider
from .pipeline_types import _ProjectedBucket, _ProjectedEvent, _ValuedEvent, _ValuedProjectedLeg


def value_projected_event(
    projected_event: _ProjectedEvent,
    *,
    eur_asset_id: AssetId,
    price_provider: PriceProvider,
) -> _ValuedEvent:
    non_fee_values = _value_non_fee_buckets(
        projected_event,
        eur_asset_id=eur_asset_id,
        price_provider=price_provider,
    )
    solved_non_fee_rates_by_asset = {
        bucket.asset_id: non_fee_values[bucket.asset_id] / bucket.quantity_total
        for bucket in projected_event.non_fee_buckets
    }
    valued_non_fee_legs = tuple(
        valued_leg
        for bucket in projected_event.non_fee_buckets
        for valued_leg in _value_bucket_legs(bucket, value_total_eur=non_fee_values[bucket.asset_id])
    )

    valued_fee_legs = tuple(
        valued_leg
        for bucket in projected_event.fee_buckets
        for valued_leg in _value_bucket_legs(
            bucket,
            value_total_eur=_value_fee_bucket(
                bucket,
                projected_event=projected_event,
                solved_non_fee_rates_by_asset=solved_non_fee_rates_by_asset,
                price_provider=price_provider,
            ),
        )
    )

    return _ValuedEvent(
        event_origin=projected_event.event_origin,
        timestamp=projected_event.timestamp,
        valued_non_fee_legs=valued_non_fee_legs,
        valued_fee_legs=valued_fee_legs,
        solved_non_fee_rates_by_asset=solved_non_fee_rates_by_asset,
    )


def _value_non_fee_buckets(
    projected_event: _ProjectedEvent,
    *,
    eur_asset_id: AssetId,
    price_provider: PriceProvider,
) -> dict[AssetId, Decimal]:
    if projected_event.exact_eur is not None and len(projected_event.non_fee_buckets) == 1:
        (bucket,) = projected_event.non_fee_buckets
        return {bucket.asset_id: projected_event.exact_eur.amount}

    return {
        bucket.asset_id: price_provider.rate(bucket.asset_id, eur_asset_id, projected_event.timestamp)
        * bucket.quantity_total
        for bucket in projected_event.non_fee_buckets
    }


def _value_fee_bucket(
    bucket: _ProjectedBucket,
    *,
    projected_event: _ProjectedEvent,
    solved_non_fee_rates_by_asset: dict[AssetId, Decimal],
    price_provider: PriceProvider,
) -> Decimal:
    if bucket.asset_id in solved_non_fee_rates_by_asset:
        return solved_non_fee_rates_by_asset[bucket.asset_id] * bucket.quantity_total
    return price_provider.rate(bucket.asset_id, AssetId("EUR"), projected_event.timestamp) * bucket.quantity_total


def _value_bucket_legs(bucket: _ProjectedBucket, *, value_total_eur: Decimal) -> tuple[_ValuedProjectedLeg, ...]:
    remaining_value = value_total_eur
    valued_legs: list[_ValuedProjectedLeg] = []

    for projected_leg in bucket.legs[:-1]:
        leg_value = value_total_eur * projected_leg.quantity / bucket.quantity_total
        remaining_value -= leg_value
        valued_legs.append(
            _ValuedProjectedLeg(
                leg=projected_leg.leg,
                kind=projected_leg.kind,
                quantity=projected_leg.quantity,
                value_total_eur=leg_value,
            )
        )

    last_leg = bucket.legs[-1]
    valued_legs.append(
        _ValuedProjectedLeg(
            leg=last_leg.leg,
            kind=last_leg.kind,
            quantity=last_leg.quantity,
            value_total_eur=remaining_value,
        )
    )
    return tuple(valued_legs)
