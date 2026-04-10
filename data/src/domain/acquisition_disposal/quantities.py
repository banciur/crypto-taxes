from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from operator import gt, lt

from ..ledger import AssetId, LedgerEvent, LedgerLeg
from .constants import BASE_CURRENCY_ASSET_ID
from .pipeline_types import (
    _ProjectedBucket,
    _ProjectedEvent,
    _ProjectedLeg,
)


def project_event_quantities(event: LedgerEvent) -> _ProjectedEvent:
    base_currency_legs: list[LedgerLeg] = []
    non_fee_legs_by_asset: dict[AssetId, list[LedgerLeg]] = defaultdict(list)
    fee_buckets: list[_ProjectedBucket] = []

    for leg in event.legs:
        if leg.is_fee:
            fee_buckets.append(
                _ProjectedBucket(
                    asset_id=leg.asset_id,
                    is_fee=True,
                    legs=(_ProjectedLeg(account_chain_id=leg.account_chain_id, quantity=leg.quantity),),
                )
            )
        elif leg.asset_id == BASE_CURRENCY_ASSET_ID:
            base_currency_legs.append(leg)
        else:
            non_fee_legs_by_asset[leg.asset_id].append(leg)

    non_fee_buckets = [
        bucket
        for asset_legs in non_fee_legs_by_asset.values()
        if (bucket := _project_asset_bucket(asset_legs)) is not None
    ]
    non_fee_buckets.sort(key=lambda bucket: (bucket.asset_id, _bucket_quantity(bucket)))
    fee_buckets.sort(key=lambda bucket: (bucket.asset_id, _bucket_quantity(bucket), bucket.legs[0].account_chain_id))

    return _ProjectedEvent(
        non_fee_buckets=tuple(non_fee_buckets),
        fee_buckets=tuple(fee_buckets),
        exact_base_currency=_project_exact_base_currency(base_currency_legs),
    )


def _project_asset_bucket(legs: list[LedgerLeg]) -> _ProjectedBucket | None:
    net_quantity = sum((leg.quantity for leg in legs), start=Decimal(0))
    if net_quantity == 0:
        return None

    op = gt if net_quantity > 0 else lt
    relevant_legs = sorted((leg for leg in legs if op(leg.quantity, 0)), key=lambda leg: leg.leg_key)

    total_raw_quantity = sum((leg.quantity for leg in relevant_legs), start=Decimal(0))
    remaining_quantity = net_quantity
    projected_legs: list[_ProjectedLeg] = []

    for leg in relevant_legs[:-1]:
        allocated_quantity = net_quantity * leg.quantity / total_raw_quantity
        remaining_quantity -= allocated_quantity
        projected_legs.append(
            _ProjectedLeg(
                account_chain_id=leg.account_chain_id,
                quantity=allocated_quantity,
            )
        )

    projected_legs.append(
        _ProjectedLeg(
            account_chain_id=relevant_legs[-1].account_chain_id,
            quantity=remaining_quantity,
        )
    )

    return _ProjectedBucket(
        asset_id=legs[0].asset_id,
        is_fee=False,
        legs=tuple(projected_legs),
    )


def _project_exact_base_currency(legs: list[LedgerLeg]) -> Decimal | None:
    net_quantity = sum((leg.quantity for leg in legs), start=Decimal(0))
    if net_quantity == 0:
        return None

    return net_quantity


def _bucket_quantity(bucket: _ProjectedBucket) -> Decimal:
    return sum((leg.quantity for leg in bucket.legs), start=Decimal(0))
