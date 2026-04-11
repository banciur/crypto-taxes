from __future__ import annotations

from collections import deque
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from ..ledger import AccountChainId, AssetId, EventOrigin
from .constants import is_fifo_tracked_asset
from .errors import AcquisitionDisposalProjectionError
from .models import AcquisitionLot, DisposalLink
from .pipeline_types import _LotBalance, _ProjectedEvent


def match_event_fifo(
    projected_event: _ProjectedEvent,
    *,
    prices: dict[AssetId, Decimal],
    event_origin: EventOrigin,
    timestamp: datetime,
    open_lots_by_asset: dict[AssetId, deque[_LotBalance]],
    acquisitions: list[AcquisitionLot],
    disposals: list[DisposalLink],
) -> None:
    for group in projected_event.all_groups:
        if not is_fifo_tracked_asset(group.asset_id):
            continue
        for projected_leg in group.legs:
            if projected_leg.quantity >= 0:
                continue

            for lot_state, take_quantity in _consume_open_lots(
                asset_id=group.asset_id,
                account_chain_id=projected_leg.account_chain_id,
                event_origin=event_origin,
                timestamp=timestamp,
                quantity_needed=abs(projected_leg.quantity),
                open_lots_by_asset=open_lots_by_asset,
            ):
                disposals.append(
                    DisposalLink(
                        lot_id=lot_state.lot.id,
                        event_origin=event_origin,
                        account_chain_id=projected_leg.account_chain_id,
                        asset_id=group.asset_id,
                        is_fee=group.is_fee,
                        timestamp=timestamp,
                        quantity_used=take_quantity,
                        # TODO: Preserve the projected disposal total exactly by assigning
                        # the rounding remainder to the final FIFO fragment.
                        proceeds_total=prices[group.asset_id] * take_quantity,
                    )
                )

    for group in projected_event.all_groups:
        if not is_fifo_tracked_asset(group.asset_id):
            continue
        for projected_leg in group.legs:
            if projected_leg.quantity <= 0:
                continue

            lot = AcquisitionLot(
                event_origin=event_origin,
                account_chain_id=projected_leg.account_chain_id,
                asset_id=group.asset_id,
                is_fee=group.is_fee,
                timestamp=timestamp,
                quantity_acquired=abs(projected_leg.quantity),
                cost_per_unit=prices[group.asset_id],
            )
            acquisitions.append(lot)
            open_lots_by_asset[group.asset_id].append(
                _LotBalance(
                    lot=lot,
                    remaining_quantity=abs(projected_leg.quantity),
                )
            )


def _consume_open_lots(
    *,
    asset_id: AssetId,
    account_chain_id: AccountChainId,
    event_origin: EventOrigin,
    timestamp: datetime,
    quantity_needed: Decimal,
    open_lots_by_asset: dict[AssetId, deque[_LotBalance]],
) -> Iterable[tuple[_LotBalance, Decimal]]:
    open_lots = open_lots_by_asset.get(asset_id)
    remaining = quantity_needed

    while remaining > 0:
        if not open_lots:
            raise _matching_error(
                "Not enough open lots",
                asset_id=asset_id,
                account_chain_id=account_chain_id,
                event_origin=event_origin,
                timestamp=timestamp,
                quantity_needed=remaining,
            )

        lot_state = open_lots[0]
        take_quantity = min(remaining, lot_state.remaining_quantity)
        lot_state.remaining_quantity -= take_quantity
        remaining -= take_quantity
        if lot_state.remaining_quantity == 0:
            open_lots.popleft()
        yield lot_state, take_quantity


def _matching_error(
    reason: str,
    *,
    asset_id: AssetId,
    account_chain_id: AccountChainId,
    event_origin: EventOrigin,
    timestamp: datetime,
    quantity_needed: Decimal | None = None,
) -> AcquisitionDisposalProjectionError:
    return AcquisitionDisposalProjectionError(
        f"{reason} for asset={asset_id} account={account_chain_id} "
        f"event_origin={event_origin.location.value}/{event_origin.external_id} "
        f"@{timestamp.isoformat()}",
        quantity_needed=quantity_needed,
    )
