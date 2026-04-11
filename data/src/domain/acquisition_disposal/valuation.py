from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from ..ledger import AssetId
from ..pricing import PriceProvider
from .constants import BASE_CURRENCY_ASSET_ID, is_valuation_anchor
from .errors import AcquisitionDisposalProjectionError
from .pipeline_types import _ProjectedAssetGroup, _ProjectedEvent


def value_projected_event(
    projected_event: _ProjectedEvent,
    *,
    timestamp: datetime,
    price_provider: PriceProvider,
) -> dict[AssetId, Decimal]:
    non_fee_prices = _value_non_fee_groups(
        projected_event,
        timestamp=timestamp,
        price_provider=price_provider,
    )
    fee_prices = _value_fee_groups(
        projected_event.fee_groups,
        non_fee_prices=non_fee_prices,
        timestamp=timestamp,
        price_provider=price_provider,
    )
    return non_fee_prices | fee_prices


def _value_non_fee_groups(
    projected_event: _ProjectedEvent,
    *,
    timestamp: datetime,
    price_provider: PriceProvider,
) -> dict[AssetId, Decimal]:
    if not projected_event.non_fee_groups:
        return {}

    direct_rates: dict[AssetId, Decimal] = {}
    unknown_groups: list[_ProjectedAssetGroup] = []

    for group in projected_event.non_fee_groups:
        direct_rate = _try_direct_rate(
            asset_id=group.asset_id,
            timestamp=timestamp,
            price_provider=price_provider,
        )
        if direct_rate is None:
            unknown_groups.append(group)
        else:
            direct_rates[group.asset_id] = direct_rate

    if len(unknown_groups) > 1:
        raise AcquisitionDisposalProjectionError(
            "More than one distinct non-fee asset is unpriceable in the same event."
        )

    if unknown_groups:
        unknown_group = unknown_groups[0]
        if is_valuation_anchor(unknown_group.asset_id):
            raise AcquisitionDisposalProjectionError(
                f"Valuation anchor asset cannot be priced directly in EUR: asset={unknown_group.asset_id}."
            )
        solved_rate = _solve_unknown_rate(
            projected_event.non_fee_groups,
            direct_rates=direct_rates,
            unknown_group=unknown_group,
        )
        return direct_rates | {unknown_group.asset_id: solved_rate}

    return _rebalance_known_rates(
        projected_event.non_fee_groups,
        direct_rates=direct_rates,
    )


def _value_fee_groups(
    fee_groups: Sequence[_ProjectedAssetGroup],
    *,
    non_fee_prices: dict[AssetId, Decimal],
    timestamp: datetime,
    price_provider: PriceProvider,
) -> dict[AssetId, Decimal]:
    fee_prices: dict[AssetId, Decimal] = {}

    for group in fee_groups:
        if group.asset_id in fee_prices:
            continue
        if group.asset_id in non_fee_prices:
            fee_prices[group.asset_id] = non_fee_prices[group.asset_id]
            continue

        direct_rate = _try_direct_rate(
            asset_id=group.asset_id,
            timestamp=timestamp,
            price_provider=price_provider,
        )
        if direct_rate is None:
            raise AcquisitionDisposalProjectionError(
                f"Fee asset appears only in fee legs and cannot be priced in EUR: asset={group.asset_id}."
            )
        fee_prices[group.asset_id] = direct_rate

    return fee_prices


def _rebalance_known_rates(
    groups: Sequence[_ProjectedAssetGroup],
    *,
    direct_rates: dict[AssetId, Decimal],
) -> dict[AssetId, Decimal]:
    acquisition_anchor_groups = _groups_for_side(groups, side=1, anchor_only=True)
    acquisition_adjustable_groups = _groups_for_side(groups, side=1, anchor_only=False)
    disposal_anchor_groups = _groups_for_side(groups, side=-1, anchor_only=True)
    disposal_adjustable_groups = _groups_for_side(groups, side=-1, anchor_only=False)

    acquisition_anchor_total = _groups_total(acquisition_anchor_groups, rates=direct_rates)
    acquisition_adjustable_total = _groups_total(acquisition_adjustable_groups, rates=direct_rates)
    disposal_anchor_total = _groups_total(disposal_anchor_groups, rates=direct_rates)
    disposal_adjustable_total = _groups_total(disposal_adjustable_groups, rates=direct_rates)

    acquisition_total = acquisition_anchor_total + acquisition_adjustable_total
    disposal_total = disposal_anchor_total + disposal_adjustable_total

    balanced_rates = dict(direct_rates)

    if acquisition_total == 0 or disposal_total == 0:
        return balanced_rates

    if acquisition_adjustable_total > 0 and disposal_adjustable_total > 0:
        target_total = (acquisition_total + disposal_total) / Decimal(2)
        _apply_target_total(
            balanced_rates,
            groups=acquisition_adjustable_groups,
            direct_rates=direct_rates,
            target_total=target_total - acquisition_anchor_total,
        )
        _apply_target_total(
            balanced_rates,
            groups=disposal_adjustable_groups,
            direct_rates=direct_rates,
            target_total=target_total - disposal_anchor_total,
        )
        return balanced_rates

    if acquisition_adjustable_total > 0:
        _apply_target_total(
            balanced_rates,
            groups=acquisition_adjustable_groups,
            direct_rates=direct_rates,
            target_total=disposal_total - acquisition_anchor_total,
        )
        return balanced_rates

    if disposal_adjustable_total > 0:
        _apply_target_total(
            balanced_rates,
            groups=disposal_adjustable_groups,
            direct_rates=direct_rates,
            target_total=acquisition_total - disposal_anchor_total,
        )
        return balanced_rates

    if acquisition_total != disposal_total:
        raise AcquisitionDisposalProjectionError(
            "Non-fee event totals disagree and cannot be rebalanced because both sides are fully anchored."
        )
    return balanced_rates


def _solve_unknown_rate(
    groups: Sequence[_ProjectedAssetGroup],
    *,
    direct_rates: dict[AssetId, Decimal],
    unknown_group: _ProjectedAssetGroup,
) -> Decimal:
    known_acquisition_total = _side_total(groups, rates=direct_rates, side=1)
    known_disposal_total = _side_total(groups, rates=direct_rates, side=-1)

    if _group_side(unknown_group) > 0:
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
            f"Remainder solving would produce a negative value for asset={unknown_group.asset_id}."
        )

    return unknown_total / abs(_group_net_quantity(unknown_group))


def _side_total(
    groups: Sequence[_ProjectedAssetGroup],
    *,
    rates: dict[AssetId, Decimal],
    side: int,
) -> Decimal:
    return sum(
        (
            _direct_total(group, rate=rates[group.asset_id])
            for group in groups
            if _group_side(group) == side and group.asset_id in rates
        ),
        start=Decimal(0),
    )


def _groups_for_side(
    groups: Sequence[_ProjectedAssetGroup],
    *,
    side: int,
    anchor_only: bool,
) -> list[_ProjectedAssetGroup]:
    return [
        group for group in groups if _group_side(group) == side and is_valuation_anchor(group.asset_id) is anchor_only
    ]


def _groups_total(
    groups: Sequence[_ProjectedAssetGroup],
    *,
    rates: dict[AssetId, Decimal],
) -> Decimal:
    return sum((_direct_total(group, rate=rates[group.asset_id]) for group in groups), start=Decimal(0))


def _apply_target_total(
    balanced_rates: dict[AssetId, Decimal],
    *,
    groups: Sequence[_ProjectedAssetGroup],
    direct_rates: dict[AssetId, Decimal],
    target_total: Decimal,
) -> None:
    if target_total <= 0:
        raise AcquisitionDisposalProjectionError(
            "Balancing would require a non-positive EUR value for adjustable non-fee assets."
        )

    current_total = _groups_total(groups, rates=direct_rates)
    if current_total <= 0:
        raise AcquisitionDisposalProjectionError(
            "One-sided event relies on direct price service valuation and the price is unavailable."
        )

    remaining_total = target_total
    for group in groups[:-1]:
        scaled_total = target_total * _direct_total(group, rate=direct_rates[group.asset_id]) / current_total
        remaining_total -= scaled_total
        balanced_rates[group.asset_id] = scaled_total / abs(_group_net_quantity(group))

    final_group = groups[-1]
    balanced_rates[final_group.asset_id] = remaining_total / abs(_group_net_quantity(final_group))


def _direct_total(group: _ProjectedAssetGroup, *, rate: Decimal) -> Decimal:
    return rate * abs(_group_net_quantity(group))


def _group_side(group: _ProjectedAssetGroup) -> int:
    return 1 if _group_net_quantity(group) > 0 else -1


def _group_net_quantity(group: _ProjectedAssetGroup) -> Decimal:
    return sum((leg.quantity for leg in group.legs), start=Decimal(0))


def _try_direct_rate(
    *,
    asset_id: AssetId,
    timestamp: datetime,
    price_provider: PriceProvider,
) -> Decimal | None:
    if asset_id == BASE_CURRENCY_ASSET_ID:
        return Decimal(1)
    try:
        return price_provider.rate(asset_id, BASE_CURRENCY_ASSET_ID, timestamp)
    except Exception:
        return None
