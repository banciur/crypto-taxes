from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from ..ledger import AccountChainId, AssetId, EventOrigin, LotId
from .constants import is_fifo_tracked_asset
from .errors import AcquisitionDisposalProjectionError
from .models import AcquisitionLot, DisposalLink
from .pipeline_types import _LotBalance, _ProjectedEvent

QUANTITY_NEEDED_MESSAGE_SUFFIX = " quantity_needed={quantity_needed}"


@dataclass(frozen=True)
class _TrackedResidual:
    asset_id: AssetId
    account_chain_id: AccountChainId
    quantity: Decimal
    is_fee: bool


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
    disposal_residuals, acquisition_residuals = _classify_fifo_residuals(projected_event)

    _match_fifo_disposals(
        residuals=disposal_residuals,
        prices=prices,
        event_origin=event_origin,
        timestamp=timestamp,
        open_lots_by_asset=open_lots_by_asset,
        disposals=disposals,
    )
    _match_fifo_acquisitions(
        residuals=acquisition_residuals,
        prices=prices,
        event_origin=event_origin,
        timestamp=timestamp,
        open_lots_by_asset=open_lots_by_asset,
        acquisitions=acquisitions,
    )


def _classify_fifo_residuals(projected_event: _ProjectedEvent) -> tuple[list[_TrackedResidual], list[_TrackedResidual]]:
    disposal_residuals: list[_TrackedResidual] = []
    acquisition_residuals: list[_TrackedResidual] = []

    for is_fee, groups in ((False, projected_event.non_fee_groups), (True, projected_event.fee_groups)):
        for group in groups:
            if not is_fifo_tracked_asset(group.asset_id):
                continue
            for residual in group.residuals:
                tracked_residual = _TrackedResidual(
                    asset_id=group.asset_id,
                    account_chain_id=residual.account_chain_id,
                    quantity=residual.quantity,
                    is_fee=is_fee,
                )
                if residual.quantity < 0:
                    disposal_residuals.append(tracked_residual)
                else:
                    acquisition_residuals.append(tracked_residual)

    return disposal_residuals, acquisition_residuals


def _match_fifo_disposals(
    *,
    residuals: Iterable[_TrackedResidual],
    prices: dict[AssetId, Decimal],
    event_origin: EventOrigin,
    timestamp: datetime,
    open_lots_by_asset: dict[AssetId, deque[_LotBalance]],
    disposals: list[DisposalLink],
) -> None:
    for residual in residuals:
        for lot_id, take_quantity in _consume_open_lots(
            asset_id=residual.asset_id,
            account_chain_id=residual.account_chain_id,
            event_origin=event_origin,
            timestamp=timestamp,
            quantity_needed=abs(residual.quantity),
            open_lots_by_asset=open_lots_by_asset,
        ):
            disposals.append(
                DisposalLink(
                    lot_id=lot_id,
                    event_origin=event_origin,
                    account_chain_id=residual.account_chain_id,
                    asset_id=residual.asset_id,
                    is_fee=residual.is_fee,
                    timestamp=timestamp,
                    quantity_used=take_quantity,
                    # TODO: Preserve the projected disposal total exactly by assigning
                    # the rounding remainder to the final FIFO fragment.
                    proceeds_total=prices[residual.asset_id] * take_quantity,
                )
            )


def _match_fifo_acquisitions(
    *,
    residuals: Iterable[_TrackedResidual],
    prices: dict[AssetId, Decimal],
    event_origin: EventOrigin,
    timestamp: datetime,
    open_lots_by_asset: dict[AssetId, deque[_LotBalance]],
    acquisitions: list[AcquisitionLot],
) -> None:
    for residual in residuals:
        lot = AcquisitionLot(
            event_origin=event_origin,
            account_chain_id=residual.account_chain_id,
            asset_id=residual.asset_id,
            is_fee=residual.is_fee,
            timestamp=timestamp,
            quantity_acquired=abs(residual.quantity),
            cost_per_unit=prices[residual.asset_id],
        )
        acquisitions.append(lot)
        open_lots_by_asset.setdefault(residual.asset_id, deque()).append(
            _LotBalance(
                lot=lot,
                remaining_quantity=abs(residual.quantity),
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
) -> Iterable[tuple[LotId, Decimal]]:
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
        yield lot_state.lot.id, take_quantity


def _matching_error(
    reason: str,
    *,
    asset_id: AssetId,
    account_chain_id: AccountChainId,
    event_origin: EventOrigin,
    timestamp: datetime,
    quantity_needed: Decimal | None = None,
) -> AcquisitionDisposalProjectionError:
    message = (
        f"{reason} for asset={asset_id} account={account_chain_id} "
        f"event_origin={event_origin.location.value}/{event_origin.external_id} "
        f"@{timestamp.isoformat()}"
    )
    if quantity_needed is not None:
        message += QUANTITY_NEEDED_MESSAGE_SUFFIX.format(quantity_needed=quantity_needed)
    return AcquisitionDisposalProjectionError(message, quantity_needed=quantity_needed)
