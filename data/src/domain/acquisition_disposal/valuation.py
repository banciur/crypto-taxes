from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal

from config import BASE_CURRENCY_ASSET_ID

from ..ledger import AssetId, EventOrigin
from ..pricing import PriceProvider
from .constants import ValuationTier, is_reference_priced, valuation_tier
from .errors import AcquisitionDisposalUnresolvedRatesError, AcquisitionDisposalValuationError
from .pipeline_types import _ProjectedAssetResidualGroup, _ProjectedEvent


class _DirectRateResolver:
    def __init__(
        self,
        *,
        price_provider: PriceProvider,
        overrides_by_event_origin: Mapping[EventOrigin, Mapping[AssetId, Decimal]],
    ) -> None:
        self._price_provider = price_provider
        self._overrides_by_event_origin = overrides_by_event_origin

    def rate(
        self,
        *,
        event_origin: EventOrigin,
        asset_id: AssetId,
        timestamp: datetime,
    ) -> Decimal | None:
        overrides = self._overrides_by_event_origin.get(event_origin, {})
        if asset_id in overrides:
            return overrides[asset_id]
        return self._price_provider.rate(asset_id, BASE_CURRENCY_ASSET_ID, timestamp)


def value_projected_event(
    projected_event: _ProjectedEvent,
    *,
    event_origin: EventOrigin,
    timestamp: datetime,
    rate_resolver: _DirectRateResolver,
) -> dict[AssetId, Decimal]:
    non_fee_prices = _value_non_fee_groups(
        projected_event,
        event_origin=event_origin,
        timestamp=timestamp,
        rate_resolver=rate_resolver,
        borrowed_rates={},
    )
    fee_prices = _value_fee_groups(
        projected_event.fee_groups,
        non_fee_prices=non_fee_prices,
        event_origin=event_origin,
        timestamp=timestamp,
        rate_resolver=rate_resolver,
    )
    return non_fee_prices | fee_prices


def _value_non_fee_groups(
    projected_event: _ProjectedEvent,
    *,
    event_origin: EventOrigin,
    timestamp: datetime,
    rate_resolver: _DirectRateResolver,
    borrowed_rates: Mapping[AssetId, Decimal],
) -> dict[AssetId, Decimal]:
    if not projected_event.non_fee_groups:
        return {}

    direct_rates: dict[AssetId, Decimal] = {}
    unknown_groups: list[_ProjectedAssetResidualGroup] = []

    for group in projected_event.non_fee_groups:
        direct_rate = rate_resolver.rate(
            event_origin=event_origin,
            asset_id=group.asset_id,
            timestamp=timestamp,
        )
        if direct_rate is None:
            if is_reference_priced(group.asset_id):
                raise AcquisitionDisposalValuationError(
                    f"Reference-priced asset cannot be priced directly in {BASE_CURRENCY_ASSET_ID}: "
                    f"asset={group.asset_id}."
                )
            direct_rate = borrowed_rates.get(group.asset_id)
        if direct_rate is None:
            unknown_groups.append(group)
        else:
            direct_rates[group.asset_id] = direct_rate

    if len(unknown_groups) > 1:
        asset_ids = frozenset(group.asset_id for group in unknown_groups)
        raise AcquisitionDisposalUnresolvedRatesError(
            "More than one distinct non-fee asset is unpriceable in the same event: "
            f"assets={_format_asset_ids(unknown_groups)}.",
            asset_ids=asset_ids,
        )

    if unknown_groups:
        unknown_group = unknown_groups[0]
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
    fee_groups: Sequence[_ProjectedAssetResidualGroup],
    *,
    non_fee_prices: Mapping[AssetId, Decimal],
    event_origin: EventOrigin,
    timestamp: datetime,
    rate_resolver: _DirectRateResolver,
) -> dict[AssetId, Decimal]:
    fee_prices: dict[AssetId, Decimal] = {}

    for group in fee_groups:
        if group.asset_id in fee_prices:
            continue
        if group.asset_id in non_fee_prices:
            fee_prices[group.asset_id] = non_fee_prices[group.asset_id]
            continue

        direct_rate = rate_resolver.rate(
            event_origin=event_origin,
            asset_id=group.asset_id,
            timestamp=timestamp,
        )
        if direct_rate is None:
            raise AcquisitionDisposalValuationError(
                f"Fee asset appears only in fee legs and cannot be priced in {BASE_CURRENCY_ASSET_ID}: "
                f"asset={group.asset_id}."
            )
        fee_prices[group.asset_id] = direct_rate

    return fee_prices


def _rebalance_known_rates(
    groups: Sequence[_ProjectedAssetResidualGroup],
    *,
    direct_rates: dict[AssetId, Decimal],
) -> dict[AssetId, Decimal]:
    """Move the event's least trustworthy rates until both sides agree.

    Only the weakest `ValuationTier` present in the event is adjustable; every stronger tier anchors. An event
    whose assets all sit in one tier has nothing stronger to anchor against, so all of its groups adjust.
    """
    adjustable_tier = max(valuation_tier(group.asset_id) for group in groups)

    acquisition_anchor_groups = _groups_for_side(groups, side=1, tier=adjustable_tier, adjustable=False)
    acquisition_adjustable_groups = _groups_for_side(groups, side=1, tier=adjustable_tier, adjustable=True)
    disposal_anchor_groups = _groups_for_side(groups, side=-1, tier=adjustable_tier, adjustable=False)
    disposal_adjustable_groups = _groups_for_side(groups, side=-1, tier=adjustable_tier, adjustable=True)

    acquisition_anchor_total = _groups_total(acquisition_anchor_groups, rates=direct_rates)
    acquisition_adjustable_total = _groups_total(acquisition_adjustable_groups, rates=direct_rates)
    disposal_anchor_total = _groups_total(disposal_anchor_groups, rates=direct_rates)
    disposal_adjustable_total = _groups_total(disposal_adjustable_groups, rates=direct_rates)

    acquisition_total = acquisition_anchor_total + acquisition_adjustable_total
    disposal_total = disposal_anchor_total + disposal_adjustable_total

    balanced_rates = dict(direct_rates)

    if acquisition_total == 0 or disposal_total == 0 or acquisition_total == disposal_total:
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

    raise AcquisitionDisposalValuationError(
        "Non-fee event totals disagree and cannot be rebalanced because the adjustable assets are valued at "
        f"zero: assets={_format_asset_ids(acquisition_adjustable_groups + disposal_adjustable_groups)}."
    )


def _solve_unknown_rate(
    groups: Sequence[_ProjectedAssetResidualGroup],
    *,
    direct_rates: dict[AssetId, Decimal],
    unknown_group: _ProjectedAssetResidualGroup,
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
        raise AcquisitionDisposalUnresolvedRatesError(
            "One-sided event relies on direct price service valuation and the price is unavailable: "
            f"asset={unknown_group.asset_id}.",
            asset_ids=frozenset({unknown_group.asset_id}),
        )

    unknown_total = opposite_total - same_side_total
    if unknown_total < 0:
        raise AcquisitionDisposalValuationError(
            f"Remainder solving would produce a negative value for asset={unknown_group.asset_id}."
        )

    return unknown_total / abs(_group_net_quantity(unknown_group))


def _side_total(
    groups: Sequence[_ProjectedAssetResidualGroup],
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
    groups: Sequence[_ProjectedAssetResidualGroup],
    *,
    side: int,
    tier: ValuationTier,
    adjustable: bool,
) -> list[_ProjectedAssetResidualGroup]:
    return [
        group
        for group in groups
        if _group_side(group) == side and (valuation_tier(group.asset_id) is tier) is adjustable
    ]


def _groups_total(
    groups: Sequence[_ProjectedAssetResidualGroup],
    *,
    rates: dict[AssetId, Decimal],
) -> Decimal:
    return sum((_direct_total(group, rate=rates[group.asset_id]) for group in groups), start=Decimal(0))


def _apply_target_total(
    balanced_rates: dict[AssetId, Decimal],
    *,
    groups: Sequence[_ProjectedAssetResidualGroup],
    direct_rates: dict[AssetId, Decimal],
    target_total: Decimal,
) -> None:
    if target_total <= 0:
        raise AcquisitionDisposalValuationError(
            "Balancing would require a non-positive EUR value for adjustable non-fee assets."
        )

    current_total = _groups_total(groups, rates=direct_rates)
    remaining_total = target_total
    for group in groups[:-1]:
        scaled_total = target_total * _direct_total(group, rate=direct_rates[group.asset_id]) / current_total
        remaining_total -= scaled_total
        balanced_rates[group.asset_id] = scaled_total / abs(_group_net_quantity(group))

    final_group = groups[-1]
    balanced_rates[final_group.asset_id] = remaining_total / abs(_group_net_quantity(final_group))


def _direct_total(group: _ProjectedAssetResidualGroup, *, rate: Decimal) -> Decimal:
    return rate * abs(_group_net_quantity(group))


def _group_side(group: _ProjectedAssetResidualGroup) -> int:
    return 1 if _group_net_quantity(group) > 0 else -1


def _group_net_quantity(group: _ProjectedAssetResidualGroup) -> Decimal:
    return sum((residual.quantity for residual in group.residuals), start=Decimal(0))


def _format_asset_ids(groups: Sequence[_ProjectedAssetResidualGroup]) -> str:
    return ",".join(str(group.asset_id) for group in groups)
