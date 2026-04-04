from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from errors import CryptoTaxesError

from .acquisition_disposal import AbstractAcquisitionDisposal, AcquisitionLot, DisposalLink
from .ledger import AssetId, LedgerEvent, LedgerLeg, LegKey
from .pricing import PriceProvider


class InventoryError(CryptoTaxesError):
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
    remaining_quantity: Decimal


@dataclass(frozen=True)
class InventoryResult:
    acquisition_lots: list[AcquisitionLot]
    disposal_links: list[DisposalLink]


class InventoryEngine:
    """Create acquisition lots and disposal links from ledger events."""

    EUR_ASSET_ID = AssetId("EUR")

    def __init__(
        self,
        *,
        price_provider: PriceProvider,
    ) -> None:
        self._price_provider = price_provider

    def process(self, events: Iterable[LedgerEvent]) -> InventoryResult:
        """Caller must provide events in chronological order."""
        acquisitions: list[AcquisitionLot] = []
        disposals: list[DisposalLink] = []

        open_lots_by_asset: dict[AssetId, deque[_OpenLotState]] = defaultdict(deque)

        for event in events:
            internal_transfer_leg_keys = self._internal_transfer_leg_keys(event)

            for leg in self._acquisition_legs(event, ignored_leg_keys=internal_transfer_leg_keys):
                lot = AcquisitionLot(
                    event_origin=event.event_origin,
                    account_chain_id=leg.account_chain_id,
                    asset_id=leg.asset_id,
                    is_fee=leg.is_fee,
                    timestamp=event.timestamp,
                    quantity_acquired=leg.quantity,
                    cost_per_unit=self._resolve_cost_per_unit(event, leg),
                )
                acquisitions.append(lot)

                state = _OpenLotState(
                    lot=lot,
                    remaining_quantity=leg.quantity,
                )
                open_lots_by_asset[leg.asset_id].append(state)

            for leg in self._disposal_legs(event, ignored_leg_keys=internal_transfer_leg_keys):
                qty_to_match = abs(leg.quantity)
                proceeds_per_unit = self._resolve_proceeds_per_unit(event, leg)

                for lot_state, take_quantity in self._match_inventory(
                    leg=leg,
                    event=event,
                    quantity_needed=qty_to_match,
                    open_lots_by_asset=open_lots_by_asset,
                ):
                    proceeds_total = proceeds_per_unit * take_quantity
                    disposals.append(
                        DisposalLink(
                            lot_id=lot_state.lot.id,
                            event_origin=event.event_origin,
                            account_chain_id=leg.account_chain_id,
                            asset_id=leg.asset_id,
                            is_fee=leg.is_fee,
                            timestamp=event.timestamp,
                            quantity_used=take_quantity,
                            proceeds_total=proceeds_total,
                        )
                    )

                    qty_to_match -= take_quantity

        acquisitions.sort(key=self._projection_sort_key)
        disposals.sort(key=self._projection_sort_key)

        return InventoryResult(
            acquisition_lots=acquisitions,
            disposal_links=disposals,
        )

    def _resolve_cost_per_unit(self, event: LedgerEvent, leg: LedgerLeg) -> Decimal:
        eur_leg = self._find_unique_eur_leg(
            event,
            expected_sign=-1,
            exclude_leg_keys={leg.leg_key},
        )
        if eur_leg is not None:
            return abs(eur_leg.quantity) / leg.quantity

        rate = self._price_provider.rate(leg.asset_id, self.EUR_ASSET_ID, event.timestamp)
        return rate

    def _resolve_proceeds_per_unit(self, event: LedgerEvent, leg: LedgerLeg) -> Decimal:
        eur_leg = self._find_unique_eur_leg(
            event,
            expected_sign=1,
            exclude_leg_keys={leg.leg_key},
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
        exclude_leg_keys: set[LegKey],
    ) -> LedgerLeg | None:
        """Locate a single EUR leg matching the expected sign (+/-).

        Returns None if none (or multiple) is found to avoid ambiguous matching.
        """
        matches = [
            leg
            for leg in event.legs
            if leg.leg_key not in exclude_leg_keys
            and not leg.is_fee
            and leg.asset_id == self.EUR_ASSET_ID
            and (leg.quantity > 0 if expected_sign > 0 else leg.quantity < 0)
        ]

        if len(matches) == 1:
            return matches[0]
        return None

    def _internal_transfer_leg_keys(self, event: LedgerEvent) -> set[LegKey]:
        by_asset: dict[AssetId, list[LedgerLeg]] = defaultdict(list)
        for leg in event.legs:
            if leg.asset_id == self.EUR_ASSET_ID or leg.is_fee:
                continue
            by_asset[leg.asset_id].append(leg)

        transfer_leg_keys: set[LegKey] = set()
        for legs in by_asset.values():
            incoming = [leg for leg in legs if leg.quantity > 0]
            outgoing = [leg for leg in legs if leg.quantity < 0]
            if not incoming or not outgoing:
                continue
            incoming_total = sum((leg.quantity for leg in incoming), start=Decimal("0"))
            outgoing_total = sum((abs(leg.quantity) for leg in outgoing), start=Decimal("0"))
            if incoming_total != outgoing_total:
                continue
            transfer_leg_keys.update(leg.leg_key for leg in incoming)
            transfer_leg_keys.update(leg.leg_key for leg in outgoing)
        return transfer_leg_keys

    def _acquisition_legs(
        self,
        event: LedgerEvent,
        *,
        ignored_leg_keys: set[LegKey],
    ) -> list[LedgerLeg]:
        acquisition_legs = [
            leg
            for leg in event.legs
            if leg.leg_key not in ignored_leg_keys and leg.quantity > 0 and leg.asset_id != self.EUR_ASSET_ID
        ]
        return sorted(acquisition_legs, key=lambda leg: leg.leg_key)

    def _disposal_legs(
        self,
        event: LedgerEvent,
        *,
        ignored_leg_keys: set[LegKey],
    ) -> list[LedgerLeg]:
        disposal_legs = [
            leg
            for leg in event.legs
            if leg.leg_key not in ignored_leg_keys and leg.quantity < 0 and leg.asset_id != self.EUR_ASSET_ID
        ]
        return sorted(disposal_legs, key=lambda leg: leg.leg_key)

    def _match_inventory(
        self,
        *,
        leg: LedgerLeg,
        event: LedgerEvent,
        quantity_needed: Decimal,
        open_lots_by_asset: dict[AssetId, deque[_OpenLotState]],
    ) -> Iterable[tuple[_OpenLotState, Decimal]]:
        open_lots = open_lots_by_asset.get(leg.asset_id)
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

    @staticmethod
    def _inventory_error(
        reason: str,
        *,
        leg: LedgerLeg,
        event: LedgerEvent,
        quantity_needed: Decimal | None = None,
    ) -> InventoryError:
        legs_summary = "; ".join(f"{leg.asset_id}:{leg.quantity}{' fee' if leg.is_fee else ''}" for leg in event.legs)
        return InventoryError(
            f"{reason} for asset={leg.asset_id} account={leg.account_chain_id} "
            f"event_origin={event.event_origin.location.value}/{event.event_origin.external_id} "
            f"@{event.timestamp.isoformat()} "
            f"legs={legs_summary}",
            leg=leg,
            event=event,
            quantity_needed=quantity_needed,
        )

    @staticmethod
    def _projection_sort_key(item: AbstractAcquisitionDisposal) -> tuple[datetime, str, str, str, str, bool]:
        return (
            item.timestamp,
            item.event_origin.location.value,
            item.event_origin.external_id,
            item.account_chain_id,
            item.asset_id,
            item.is_fee,
        )
