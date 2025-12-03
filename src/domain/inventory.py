from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from pydantic import BaseModel

from .ledger import AcquisitionLot, DisposalLink, EventType, LedgerEvent, LedgerLeg
from .pricing import PriceProvider
from .wallet_balance_tracker import WalletBalanceError, WalletBalanceTracker


class InventoryError(Exception):
    def __init__(
        self,
        message: str,
        *,
        leg: LedgerLeg | None = None,
        event: LedgerEvent | None = None,
        quantity_needed: Decimal | None = None,
    ) -> None:
        super().__init__(message)
        self.leg = leg
        self.event = event
        self.quantity_needed = quantity_needed


@dataclass
class _OpenLotState:
    lot: AcquisitionLot
    asset_id: str
    acquired_timestamp: datetime
    remaining_quantity: Decimal


class OpenLotSnapshot(BaseModel):
    lot_id: UUID
    asset_id: str
    acquired_timestamp: datetime
    quantity_remaining: Decimal
    cost_per_unit: Decimal


class InventoryResult(BaseModel):
    acquisition_lots: list[AcquisitionLot]
    disposal_links: list[DisposalLink]
    open_inventory: list[OpenLotSnapshot]


class InventoryEngine:
    """Create acquisition lots and disposal links from ledger events."""

    EUR_ASSET_ID = "EUR"

    def __init__(self, *, price_provider: PriceProvider) -> None:
        self._price_provider = price_provider

    def process(self, events: Iterable[LedgerEvent]) -> InventoryResult:
        """Caller must provide events in chronological order."""
        acquisitions: list[AcquisitionLot] = []
        disposals: list[DisposalLink] = []

        inventory: dict[str, deque[_OpenLotState]] = defaultdict(deque)
        wallet_balances = WalletBalanceTracker()

        for event in events:
            self._apply_wallet_movements(event, wallet_balances)

            if event.event_type == EventType.TRANSFER:
                continue

            acquisition_legs = [leg for leg in event.legs if leg.quantity > 0 and leg.asset_id != self.EUR_ASSET_ID]
            for leg in acquisition_legs:
                lot = AcquisitionLot(
                    acquired_leg_id=leg.id,
                    cost_per_unit=self._resolve_cost_per_unit(event, leg),
                )
                acquisitions.append(lot)

                state = _OpenLotState(
                    lot=lot,
                    asset_id=leg.asset_id,
                    acquired_timestamp=event.timestamp,
                    remaining_quantity=leg.quantity,
                )
                self._append_open_lot_state(inventory, state)

            disposal_legs = [leg for leg in event.legs if leg.quantity < 0 and leg.asset_id != self.EUR_ASSET_ID]
            for leg in disposal_legs:
                qty_to_match = abs(leg.quantity)
                proceeds_per_unit = self._resolve_proceeds_per_unit(event, leg)

                for lot_state, take_quantity in self._match_inventory(
                    leg=leg,
                    event=event,
                    quantity_needed=qty_to_match,
                    inventory=inventory,
                ):
                    proceeds_total = proceeds_per_unit * take_quantity
                    disposals.append(
                        DisposalLink(
                            disposal_leg_id=leg.id,
                            lot_id=lot_state.lot.id,
                            quantity_used=take_quantity,
                            proceeds_total=proceeds_total,
                        )
                    )

                    qty_to_match -= take_quantity

        open_inventory_snapshots = [
            OpenLotSnapshot(
                lot_id=state.lot.id,
                asset_id=state.asset_id,
                acquired_timestamp=state.acquired_timestamp,
                quantity_remaining=state.remaining_quantity,
                cost_per_unit=state.lot.cost_per_unit,
            )
            for states in inventory.values()
            for state in states
        ]

        open_inventory_snapshots.sort(key=lambda snap: (snap.asset_id, snap.acquired_timestamp))

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
        """Locate a single EUR leg matching the expected sign (+/-).

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

    def _match_inventory(
        self,
        *,
        leg: LedgerLeg,
        event: LedgerEvent,
        quantity_needed: Decimal,
        inventory: dict[str, deque[_OpenLotState]],
    ) -> Iterable[tuple[_OpenLotState, Decimal]]:
        open_lots = inventory.get(leg.asset_id)
        if not open_lots:
            raise self._inventory_error("No open lots", leg=leg, event=event, quantity_needed=quantity_needed)

        remaining = quantity_needed
        while remaining > 0:
            if not open_lots:
                raise self._inventory_error("Not enough inventory", leg=leg, event=event)

            lot_state = open_lots[0]
            take_quantity = min(remaining, lot_state.remaining_quantity)
            lot_state.remaining_quantity -= take_quantity
            remaining -= take_quantity
            if lot_state.remaining_quantity == 0:
                open_lots.popleft()
            yield lot_state, take_quantity

    def _inventory_error(
        self,
        reason: str,
        *,
        leg: LedgerLeg,
        event: LedgerEvent,
        quantity_needed: Decimal | None = None,
    ) -> InventoryError:
        legs_summary = "; ".join(f"{leg.asset_id}:{leg.quantity}{' fee' if leg.is_fee else ''}" for leg in event.legs)
        return InventoryError(
            f"{reason} for asset={leg.asset_id} wallet={leg.wallet_id} leg={leg.id} event={event.id} "
            f"{event.event_type} @{event.timestamp.isoformat()} "
            f"legs={legs_summary}",
            leg=leg,
            event=event,
            quantity_needed=quantity_needed,
        )

    def _apply_wallet_movements(
        self,
        event: LedgerEvent,
        wallet_balances: WalletBalanceTracker,
    ) -> None:
        for leg in event.legs:
            if leg.asset_id == self.EUR_ASSET_ID:
                continue
            try:
                wallet_balances.apply_movement(
                    asset_id=leg.asset_id,
                    wallet_id=leg.wallet_id,
                    quantity=leg.quantity,
                )
            except WalletBalanceError as err:
                quantity_needed = None
                if leg.quantity < 0:
                    missing = abs(leg.quantity) - err.available_balance
                    quantity_needed = missing if missing > 0 else abs(leg.quantity)
                raise self._inventory_error(
                    "Insufficient wallet balance",
                    leg=leg,
                    event=event,
                    quantity_needed=quantity_needed,
                ) from err

    def _append_open_lot_state(
        self,
        inventory: dict[str, deque[_OpenLotState]],
        state: _OpenLotState,
    ) -> None:
        open_lots = inventory[state.asset_id]
        insert_at = None
        for idx, existing in enumerate(open_lots):
            if existing.acquired_timestamp > state.acquired_timestamp:
                insert_at = idx
                break

        if insert_at is None:
            open_lots.append(state)
        else:
            open_lots.insert(insert_at, state)
