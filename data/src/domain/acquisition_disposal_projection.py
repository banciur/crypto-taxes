from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from operator import gt, lt
from typing import Iterable

from errors import CryptoTaxesError

from .acquisition_disposal import AbstractAcquisitionDisposal, AcquisitionLot, DisposalLink
from .ledger import AssetId, LedgerEvent, LedgerLeg
from .pricing import PriceProvider


class AcquisitionDisposalProjectionError(CryptoTaxesError):
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
class _LotBalance:
    lot: AcquisitionLot
    remaining_quantity: Decimal


@dataclass(frozen=True)
class _ProjectedLegQuantity:
    leg: LedgerLeg
    quantity: Decimal


@dataclass(frozen=True)
class AcquisitionDisposalProjection:
    acquisition_lots: list[AcquisitionLot]
    disposal_links: list[DisposalLink]


class AcquisitionDisposalProjector:
    """Project ledger events into acquisition lots and disposal links."""

    EUR_ASSET_ID = AssetId("EUR")

    def __init__(
        self,
        *,
        price_provider: PriceProvider,
    ) -> None:
        self._price_provider = price_provider

    def project(self, events: Iterable[LedgerEvent]) -> AcquisitionDisposalProjection:
        """Caller must provide events in chronological order."""
        acquisitions: list[AcquisitionLot] = []
        disposals: list[DisposalLink] = []

        open_lots_by_asset: dict[AssetId, deque[_LotBalance]] = defaultdict(deque)

        for event in events:
            projected_legs = self._projected_non_eur_legs(event)

            for projected_leg in self._disposal_legs(projected_legs):
                qty_to_match = abs(projected_leg.quantity)
                proceeds_per_unit = self._resolve_proceeds_per_unit(event, projected_leg, projected_legs)

                for lot_state, take_quantity in self._consume_open_lots(
                    leg=projected_leg.leg,
                    event=event,
                    quantity_needed=qty_to_match,
                    open_lots_by_asset=open_lots_by_asset,
                ):
                    disposals.append(
                        DisposalLink(
                            lot_id=lot_state.lot.id,
                            event_origin=event.event_origin,
                            account_chain_id=projected_leg.leg.account_chain_id,
                            asset_id=projected_leg.leg.asset_id,
                            is_fee=projected_leg.leg.is_fee,
                            timestamp=event.timestamp,
                            quantity_used=take_quantity,
                            proceeds_total=proceeds_per_unit * take_quantity,
                        )
                    )

            for projected_leg in self._acquisition_legs(projected_legs):
                lot = AcquisitionLot(
                    event_origin=event.event_origin,
                    account_chain_id=projected_leg.leg.account_chain_id,
                    asset_id=projected_leg.leg.asset_id,
                    is_fee=projected_leg.leg.is_fee,
                    timestamp=event.timestamp,
                    quantity_acquired=projected_leg.quantity,
                    cost_per_unit=self._resolve_cost_per_unit(event, projected_leg, projected_legs),
                )
                acquisitions.append(lot)

                state = _LotBalance(
                    lot=lot,
                    remaining_quantity=projected_leg.quantity,
                )
                open_lots_by_asset[projected_leg.leg.asset_id].append(state)

        acquisitions.sort(key=self._projection_sort_key)
        disposals.sort(key=self._projection_sort_key)

        return AcquisitionDisposalProjection(
            acquisition_lots=acquisitions,
            disposal_links=disposals,
        )

    def _resolve_cost_per_unit(
        self,
        event: LedgerEvent,
        projected_leg: _ProjectedLegQuantity,
        projected_legs: list[_ProjectedLegQuantity],
    ) -> Decimal:
        eur_leg = self._find_unique_eur_leg(
            event,
            expected_sign=-1,
            allow_eur_pricing=(
                projected_leg.leg.is_fee is False
                and self._has_single_non_fee_projected_leg(projected_legs, expected_sign=1)
            ),
        )
        if eur_leg is not None:
            return abs(eur_leg.quantity) / projected_leg.quantity

        rate = self._price_provider.rate(projected_leg.leg.asset_id, self.EUR_ASSET_ID, event.timestamp)
        return rate

    def _resolve_proceeds_per_unit(
        self,
        event: LedgerEvent,
        projected_leg: _ProjectedLegQuantity,
        projected_legs: list[_ProjectedLegQuantity],
    ) -> Decimal:
        eur_leg = self._find_unique_eur_leg(
            event,
            expected_sign=1,
            allow_eur_pricing=(
                projected_leg.leg.is_fee is False
                and self._has_single_non_fee_projected_leg(projected_legs, expected_sign=-1)
            ),
        )
        if eur_leg is not None:
            return abs(eur_leg.quantity) / abs(projected_leg.quantity)

        rate = self._price_provider.rate(projected_leg.leg.asset_id, self.EUR_ASSET_ID, event.timestamp)
        return rate

    def _find_unique_eur_leg(
        self,
        event: LedgerEvent,
        *,
        expected_sign: int,
        allow_eur_pricing: bool,
    ) -> LedgerLeg | None:
        """Locate a single EUR leg matching the expected sign (+/-).

        Returns None if none (or multiple) is found to avoid ambiguous matching.
        """
        if not allow_eur_pricing:
            return None

        matches = [
            leg
            for leg in event.legs
            if not leg.is_fee
            and leg.asset_id == self.EUR_ASSET_ID
            and (leg.quantity > 0 if expected_sign > 0 else leg.quantity < 0)
        ]

        if len(matches) == 1:
            return matches[0]
        return None

    def _projected_non_eur_legs(self, event: LedgerEvent) -> list[_ProjectedLegQuantity]:
        by_asset: dict[AssetId, list[LedgerLeg]] = defaultdict(list)
        projected_legs: list[_ProjectedLegQuantity] = []

        for leg in event.legs:
            if leg.asset_id == self.EUR_ASSET_ID:
                continue
            if leg.is_fee:
                projected_legs.append(_ProjectedLegQuantity(leg=leg, quantity=leg.quantity))
                continue
            by_asset[leg.asset_id].append(leg)

        for legs in by_asset.values():
            projected_legs.extend(self._project_asset_legs(legs))

        return projected_legs

    def _project_asset_legs(self, legs: list[LedgerLeg]) -> list[_ProjectedLegQuantity]:
        net_quantity = sum((leg.quantity for leg in legs), start=Decimal(0))

        if net_quantity == 0:
            return []

        op = gt if net_quantity > 0 else lt
        relevant_legs = sorted(
            (leg for leg in legs if op(leg.quantity, 0)),
            key=lambda leg: leg.leg_key,
        )

        return self._allocate_projected_legs(relevant_legs, quantity_to_allocate=net_quantity)

    @staticmethod
    def _allocate_projected_legs(legs: list[LedgerLeg], quantity_to_allocate: Decimal) -> list[_ProjectedLegQuantity]:
        total_raw_quantity = sum((leg.quantity for leg in legs), start=Decimal(0))
        remaining_quantity = quantity_to_allocate
        projected_legs: list[_ProjectedLegQuantity] = []

        for leg in legs[:-1]:
            allocated_quantity = quantity_to_allocate * leg.quantity / total_raw_quantity
            remaining_quantity -= allocated_quantity

            projected_legs.append(
                _ProjectedLegQuantity(
                    leg=leg,
                    quantity=allocated_quantity,
                )
            )

        projected_legs.append(
            _ProjectedLegQuantity(
                leg=legs[-1],
                quantity=remaining_quantity,
            )
        )

        return projected_legs

    @staticmethod
    def _has_single_non_fee_projected_leg(
        projected_legs: list[_ProjectedLegQuantity],
        *,
        expected_sign: int,
    ) -> bool:
        matches = [
            projected_leg
            for projected_leg in projected_legs
            if projected_leg.leg.is_fee is False
            and (projected_leg.quantity > 0 if expected_sign > 0 else projected_leg.quantity < 0)
        ]

        return len(matches) == 1

    def _acquisition_legs(self, projected_legs: list[_ProjectedLegQuantity]) -> list[_ProjectedLegQuantity]:
        acquisition_legs = [projected_leg for projected_leg in projected_legs if projected_leg.quantity > 0]
        return sorted(acquisition_legs, key=lambda projected_leg: projected_leg.leg.leg_key)

    def _disposal_legs(self, projected_legs: list[_ProjectedLegQuantity]) -> list[_ProjectedLegQuantity]:
        disposal_legs = [projected_leg for projected_leg in projected_legs if projected_leg.quantity < 0]
        return sorted(disposal_legs, key=lambda projected_leg: projected_leg.leg.leg_key)

    def _consume_open_lots(
        self,
        *,
        leg: LedgerLeg,
        event: LedgerEvent,
        quantity_needed: Decimal,
        open_lots_by_asset: dict[AssetId, deque[_LotBalance]],
    ) -> Iterable[tuple[_LotBalance, Decimal]]:
        open_lots = open_lots_by_asset.get(leg.asset_id)
        remaining = quantity_needed
        while remaining > 0:
            if not open_lots:
                raise self._matching_error("Not enough open lots", leg=leg, event=event, quantity_needed=remaining)

            lot_state = open_lots[0]
            take_quantity = min(remaining, lot_state.remaining_quantity)
            lot_state.remaining_quantity -= take_quantity
            remaining -= take_quantity
            if lot_state.remaining_quantity == 0:
                open_lots.popleft()
            yield lot_state, take_quantity

    @staticmethod
    def _matching_error(
        reason: str,
        *,
        leg: LedgerLeg,
        event: LedgerEvent,
        quantity_needed: Decimal | None = None,
    ) -> AcquisitionDisposalProjectionError:
        legs_summary = "; ".join(f"{leg.asset_id}:{leg.quantity}{' fee' if leg.is_fee else ''}" for leg in event.legs)
        return AcquisitionDisposalProjectionError(
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
