from __future__ import annotations

from collections import deque
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from ..ledger import AssetId, EventOrigin, LedgerLeg
from .errors import AcquisitionDisposalProjectionError
from .models import AcquisitionLot, DisposalLink
from .pipeline_types import _LotBalance, _ProjectionKind, _ValuedEvent, _ValuedProjectedLeg


def match_event_fifo(
    valued_event: _ValuedEvent,
    *,
    open_lots_by_asset: dict[AssetId, deque[_LotBalance]],
    acquisitions: list[AcquisitionLot],
    disposals: list[DisposalLink],
) -> None:
    for valued_leg in _disposal_legs(valued_event):
        matches = list(
            _consume_open_lots(
                leg=valued_leg.leg,
                event_origin=valued_event.event_origin,
                timestamp=valued_event.timestamp,
                quantity_needed=valued_leg.quantity,
                open_lots_by_asset=open_lots_by_asset,
            )
        )
        remaining_proceeds = valued_leg.value_total_eur

        for lot_state, take_quantity in matches[:-1]:
            link_proceeds = valued_leg.value_total_eur * take_quantity / valued_leg.quantity
            remaining_proceeds -= link_proceeds
            disposals.append(
                DisposalLink(
                    lot_id=lot_state.lot.id,
                    event_origin=valued_event.event_origin,
                    account_chain_id=valued_leg.leg.account_chain_id,
                    asset_id=valued_leg.leg.asset_id,
                    is_fee=valued_leg.leg.is_fee,
                    timestamp=valued_event.timestamp,
                    quantity_used=take_quantity,
                    proceeds_total=link_proceeds,
                )
            )

        last_lot_state, last_quantity = matches[-1]
        disposals.append(
            DisposalLink(
                lot_id=last_lot_state.lot.id,
                event_origin=valued_event.event_origin,
                account_chain_id=valued_leg.leg.account_chain_id,
                asset_id=valued_leg.leg.asset_id,
                is_fee=valued_leg.leg.is_fee,
                timestamp=valued_event.timestamp,
                quantity_used=last_quantity,
                proceeds_total=remaining_proceeds,
            )
        )

    for valued_leg in _acquisition_legs(valued_event):
        lot = AcquisitionLot(
            event_origin=valued_event.event_origin,
            account_chain_id=valued_leg.leg.account_chain_id,
            asset_id=valued_leg.leg.asset_id,
            is_fee=valued_leg.leg.is_fee,
            timestamp=valued_event.timestamp,
            quantity_acquired=valued_leg.quantity,
            cost_per_unit=valued_leg.rate_eur_per_unit,
        )
        acquisitions.append(lot)
        open_lots_by_asset[valued_leg.leg.asset_id].append(
            _LotBalance(
                lot=lot,
                remaining_quantity=valued_leg.quantity,
            )
        )


def _acquisition_legs(valued_event: _ValuedEvent) -> tuple[_ValuedProjectedLeg, ...]:
    return tuple(
        valued_leg for valued_leg in valued_event.all_valued_legs if valued_leg.kind == _ProjectionKind.ACQUISITION
    )


def _disposal_legs(valued_event: _ValuedEvent) -> tuple[_ValuedProjectedLeg, ...]:
    return tuple(
        valued_leg for valued_leg in valued_event.all_valued_legs if valued_leg.kind == _ProjectionKind.DISPOSAL
    )


def _consume_open_lots(
    *,
    leg: LedgerLeg,
    event_origin: EventOrigin,
    timestamp: datetime,
    quantity_needed: Decimal,
    open_lots_by_asset: dict[AssetId, deque[_LotBalance]],
) -> Iterable[tuple[_LotBalance, Decimal]]:
    open_lots = open_lots_by_asset.get(leg.asset_id)
    remaining = quantity_needed

    while remaining > 0:
        if not open_lots:
            raise _matching_error(
                "Not enough open lots",
                leg=leg,
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
    leg: LedgerLeg,
    event_origin: EventOrigin,
    timestamp: datetime,
    quantity_needed: Decimal | None = None,
) -> AcquisitionDisposalProjectionError:
    return AcquisitionDisposalProjectionError(
        f"{reason} for asset={leg.asset_id} account={leg.account_chain_id} "
        f"event_origin={event_origin.location.value}/{event_origin.external_id} "
        f"@{timestamp.isoformat()}",
        leg=leg,
        quantity_needed=quantity_needed,
    )
