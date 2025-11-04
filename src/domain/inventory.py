from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Iterable
from uuid import UUID

from pydantic import BaseModel

from .ledger import AcquisitionLot, DisposalLink, LedgerEvent, LedgerLeg
from .pricing import PriceProvider


class InventoryError(Exception):
    pass


class LotSelectionPolicy(StrEnum):
    FIFO = "FIFO"
    HIFO = "HIFO"
    SPEC_ID = "SPEC_ID"


@dataclass
class _OpenLotState:
    lot: AcquisitionLot
    asset_id: str
    wallet_id: str
    acquired_timestamp: datetime
    remaining_quantity: Decimal


class OpenLotSnapshot(BaseModel):
    lot_id: UUID
    asset_id: str
    wallet_id: str
    acquired_timestamp: datetime
    quantity_remaining: Decimal
    cost_eur_per_unit: Decimal


class InventoryResult(BaseModel):
    acquisition_lots: list[AcquisitionLot]
    disposal_links: list[DisposalLink]
    open_inventory: list[OpenLotSnapshot]


class InventoryEngine:
    """Create acquisition lots and disposal links from ledger events.

    v1 assumptions:
    - Fees remain separate: fee legs do not adjust cost basis or proceeds.
    - EUR legs are optional; if none exist (or ambiguous), pricing falls back
      to the provided `PriceProvider`.
    - Lot scope is per (asset_id, wallet_id); cross-wallet consolidation can
      be added later if policy requires it.
    """

    EUR_ASSET_ID = "EUR"

    def __init__(
        self,
        *,
        price_provider: PriceProvider,
        lot_selection_policy: LotSelectionPolicy = LotSelectionPolicy.FIFO,
    ) -> None:
        self._price_provider = price_provider
        self._policy = lot_selection_policy

        if self._policy not in {LotSelectionPolicy.FIFO}:
            # Only FIFO is implemented. Other policies are future work.
            raise NotImplementedError(f"{self._policy} matching not implemented yet")

    def process(self, events: Iterable[LedgerEvent]) -> InventoryResult:
        """Transform ordered ledger events into lots, disposal links, and snapshots.

        Caller must provide events in chronological order; the engine preserves the
        incoming sequence instead of re-sorting internally.
        """
        acquisitions: list[AcquisitionLot] = []
        disposals: list[DisposalLink] = []

        inventory: dict[tuple[str, str], deque[_OpenLotState]] = defaultdict(deque)

        for event in events:
            acquisition_legs = [
                leg for leg in event.legs if leg.quantity > 0 and not leg.is_fee and leg.asset_id != self.EUR_ASSET_ID
            ]
            disposal_legs = [
                leg for leg in event.legs if leg.quantity < 0 and not leg.is_fee and leg.asset_id != self.EUR_ASSET_ID
            ]

            for leg in acquisition_legs:
                cost_per_unit = self._resolve_cost_per_unit(event, leg)
                lot = AcquisitionLot(
                    acquired_event_id=event.id,
                    acquired_leg_id=leg.id,
                    cost_eur_per_unit=cost_per_unit,
                )

                state = _OpenLotState(
                    lot=lot,
                    asset_id=leg.asset_id,
                    wallet_id=leg.wallet_id,
                    acquired_timestamp=event.timestamp,
                    remaining_quantity=leg.quantity,
                )

                acquisitions.append(lot)
                inventory[(leg.asset_id, leg.wallet_id)].append(state)

            for leg in disposal_legs:
                qty_to_match = abs(leg.quantity)
                proceeds_per_unit = self._resolve_proceeds_per_unit(event, leg)

                open_lots = inventory.get((leg.asset_id, leg.wallet_id))
                if not open_lots:
                    raise InventoryError(f"No open lots for asset={leg.asset_id} wallet={leg.wallet_id}")

                while qty_to_match > 0:
                    if not open_lots:
                        raise InventoryError(f"Not enough inventory for asset={leg.asset_id} wallet={leg.wallet_id}")

                    lot_state = open_lots[0]
                    take_quantity = min(qty_to_match, lot_state.remaining_quantity)

                    proceeds_total = proceeds_per_unit * take_quantity
                    disposals.append(
                        DisposalLink(
                            disposal_leg_id=leg.id,
                            lot_id=lot_state.lot.id,
                            quantity_used=take_quantity,
                            proceeds_total_eur=proceeds_total,
                        )
                    )

                    lot_state.remaining_quantity -= take_quantity
                    qty_to_match -= take_quantity

                    if lot_state.remaining_quantity == 0:
                        open_lots.popleft()

        open_inventory_snapshots = [
            OpenLotSnapshot(
                lot_id=state.lot.id,
                asset_id=state.asset_id,
                wallet_id=state.wallet_id,
                acquired_timestamp=state.acquired_timestamp,
                quantity_remaining=state.remaining_quantity,
                cost_eur_per_unit=state.lot.cost_eur_per_unit,
            )
            for states in inventory.values()
            for state in states
        ]

        open_inventory_snapshots.sort(key=lambda snap: (snap.asset_id, snap.wallet_id, snap.acquired_timestamp))

        return InventoryResult(
            acquisition_lots=acquisitions,
            disposal_links=disposals,
            open_inventory=open_inventory_snapshots,
        )

    def _resolve_cost_per_unit(self, event: LedgerEvent, leg: LedgerLeg) -> Decimal:
        eur_leg = self._find_unique_eur_leg(
            event,
            expected_sign=-1,
            exclude_leg_ids={leg.id},
        )
        if eur_leg is not None:
            return abs(eur_leg.quantity) / leg.quantity

        rate = self._price_provider.rate(leg.asset_id, self.EUR_ASSET_ID, event.timestamp)
        return rate

    def _resolve_proceeds_per_unit(self, event: LedgerEvent, leg: LedgerLeg) -> Decimal:
        eur_leg = self._find_unique_eur_leg(
            event,
            expected_sign=1,
            exclude_leg_ids={leg.id},
        )
        if eur_leg is not None:
            return abs(eur_leg.quantity) / abs(leg.quantity)

        rate = self._price_provider.rate(leg.asset_id, self.EUR_ASSET_ID, event.timestamp)
        return rate

    def _find_unique_eur_leg(
        self,
        event: LedgerEvent,
        *,
        expected_sign: int,
        exclude_leg_ids: set[UUID],
    ) -> LedgerLeg | None:
        """Locate a single non-fee EUR leg matching the expected sign (+/-).

        Returns None if none (or multiple) are found to avoid ambiguous matching.
        """
        matches = [
            leg
            for leg in event.legs
            if leg.id not in exclude_leg_ids
            and not leg.is_fee
            and leg.asset_id == self.EUR_ASSET_ID
            and (leg.quantity > 0 if expected_sign > 0 else leg.quantity < 0)
        ]

        if len(matches) == 1:
            return matches[0]
        return None
