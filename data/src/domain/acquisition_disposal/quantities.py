from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from operator import gt, lt

from ..ledger import AssetId, LedgerEvent, LedgerLeg
from .pipeline_types import (
    _ProjectedAssetGroup,
    _ProjectedEvent,
    _ProjectedResidualLeg,
)


def project_event_quantities(event: LedgerEvent) -> _ProjectedEvent:
    non_fee_legs_by_asset: dict[AssetId, list[LedgerLeg]] = defaultdict(list)
    fee_groups: list[_ProjectedAssetGroup] = []

    for leg in event.legs:
        if leg.is_fee:
            fee_groups.append(
                _ProjectedAssetGroup(
                    asset_id=leg.asset_id,
                    is_fee=True,
                    legs=[_ProjectedResidualLeg(account_chain_id=leg.account_chain_id, quantity=leg.quantity)],
                )
            )
        else:
            non_fee_legs_by_asset[leg.asset_id].append(leg)

    non_fee_groups = [
        group
        for asset_legs in non_fee_legs_by_asset.values()
        if (group := _project_asset_group(asset_legs)) is not None
    ]
    non_fee_groups.sort(key=lambda group: group.asset_id)
    fee_groups.sort(key=lambda group: (group.asset_id, group.legs[0].account_chain_id))

    return _ProjectedEvent(
        non_fee_groups=non_fee_groups,
        fee_groups=fee_groups,
    )


def _project_asset_group(legs: list[LedgerLeg]) -> _ProjectedAssetGroup | None:
    net_quantity = sum((leg.quantity for leg in legs), start=Decimal(0))
    if net_quantity == 0:
        return None

    op = gt if net_quantity > 0 else lt
    relevant_legs = sorted((leg for leg in legs if op(leg.quantity, 0)), key=lambda leg: leg.leg_key)

    total_raw_quantity = sum((leg.quantity for leg in relevant_legs), start=Decimal(0))
    remaining_quantity = net_quantity
    projected_legs: list[_ProjectedResidualLeg] = []

    for leg in relevant_legs[:-1]:
        allocated_quantity = net_quantity * leg.quantity / total_raw_quantity
        remaining_quantity -= allocated_quantity
        projected_legs.append(
            _ProjectedResidualLeg(
                account_chain_id=leg.account_chain_id,
                quantity=allocated_quantity,
            )
        )

    projected_legs.append(
        _ProjectedResidualLeg(
            account_chain_id=relevant_legs[-1].account_chain_id,
            quantity=remaining_quantity,
        )
    )

    return _ProjectedAssetGroup(
        asset_id=legs[0].asset_id,
        is_fee=False,
        legs=projected_legs,
    )
