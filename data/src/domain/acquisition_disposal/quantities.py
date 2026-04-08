from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from operator import gt, lt

from ..ledger import AssetId, LedgerEvent, LedgerLeg
from .pipeline_types import _ExactEurResidual, _ProjectedBucket, _ProjectedEvent, _ProjectedLeg, _ProjectionKind


def project_event_quantities(event: LedgerEvent, *, eur_asset_id: AssetId) -> _ProjectedEvent:
    eur_legs: list[LedgerLeg] = []
    non_fee_legs_by_asset: dict[AssetId, list[LedgerLeg]] = defaultdict(list)
    fee_buckets: list[_ProjectedBucket] = []

    for leg in event.legs:
        if leg.is_fee:
            fee_buckets.append(_project_fee_bucket(leg))
        elif leg.asset_id == eur_asset_id:
            eur_legs.append(leg)
        else:
            non_fee_legs_by_asset[leg.asset_id].append(leg)

    non_fee_buckets = [
        bucket
        for asset_legs in non_fee_legs_by_asset.values()
        if (bucket := _project_asset_bucket(asset_legs)) is not None
    ]
    non_fee_buckets.sort(key=lambda bucket: (bucket.asset_id, bucket.kind.value))
    fee_buckets.sort(key=lambda bucket: (bucket.asset_id, bucket.kind.value, bucket.legs[0].leg.leg_key))

    return _ProjectedEvent(
        event_origin=event.event_origin,
        timestamp=event.timestamp,
        non_fee_buckets=tuple(non_fee_buckets),
        fee_buckets=tuple(fee_buckets),
        exact_eur=_project_exact_eur(eur_legs),
    )


def _project_fee_bucket(leg: LedgerLeg) -> _ProjectedBucket:
    kind = _ProjectionKind.ACQUISITION if leg.quantity > 0 else _ProjectionKind.DISPOSAL
    quantity = abs(leg.quantity)
    projected_leg = _ProjectedLeg(leg=leg, kind=kind, quantity=quantity)
    return _ProjectedBucket(
        asset_id=leg.asset_id,
        kind=kind,
        is_fee=True,
        legs=(projected_leg,),
        quantity_total=quantity,
    )


def _project_asset_bucket(legs: list[LedgerLeg]) -> _ProjectedBucket | None:
    net_quantity = sum((leg.quantity for leg in legs), start=Decimal(0))
    if net_quantity == 0:
        return None

    kind = _ProjectionKind.ACQUISITION if net_quantity > 0 else _ProjectionKind.DISPOSAL
    op = gt if net_quantity > 0 else lt
    relevant_legs = sorted((leg for leg in legs if op(leg.quantity, 0)), key=lambda leg: leg.leg_key)
    quantity_total = abs(net_quantity)
    projected_legs = _allocate_projected_legs(relevant_legs, quantity_to_allocate=quantity_total, kind=kind)

    return _ProjectedBucket(
        asset_id=legs[0].asset_id,
        kind=kind,
        is_fee=False,
        legs=tuple(projected_legs),
        quantity_total=quantity_total,
    )


def _allocate_projected_legs(
    legs: list[LedgerLeg],
    *,
    quantity_to_allocate: Decimal,
    kind: _ProjectionKind,
) -> list[_ProjectedLeg]:
    total_raw_quantity = sum((abs(leg.quantity) for leg in legs), start=Decimal(0))
    remaining_quantity = quantity_to_allocate
    projected_legs: list[_ProjectedLeg] = []

    for leg in legs[:-1]:
        allocated_quantity = quantity_to_allocate * abs(leg.quantity) / total_raw_quantity
        remaining_quantity -= allocated_quantity
        projected_legs.append(_ProjectedLeg(leg=leg, kind=kind, quantity=allocated_quantity))

    projected_legs.append(_ProjectedLeg(leg=legs[-1], kind=kind, quantity=remaining_quantity))
    return projected_legs


def _project_exact_eur(legs: list[LedgerLeg]) -> _ExactEurResidual | None:
    net_quantity = sum((leg.quantity for leg in legs), start=Decimal(0))
    if net_quantity == 0:
        return None

    kind = _ProjectionKind.ACQUISITION if net_quantity > 0 else _ProjectionKind.DISPOSAL
    return _ExactEurResidual(kind=kind, amount=abs(net_quantity))
