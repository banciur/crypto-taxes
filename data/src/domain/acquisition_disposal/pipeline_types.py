from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from ..ledger import AssetId, EventOrigin, LedgerLeg
from .models import AcquisitionLot


class _ProjectionKind(StrEnum):
    ACQUISITION = "ACQUISITION"
    DISPOSAL = "DISPOSAL"


@dataclass(frozen=True)
class _ProjectedLeg:
    leg: LedgerLeg
    kind: _ProjectionKind
    quantity: Decimal


@dataclass(frozen=True)
class _ProjectedBucket:
    asset_id: AssetId
    kind: _ProjectionKind
    is_fee: bool
    legs: tuple[_ProjectedLeg, ...]
    quantity_total: Decimal


@dataclass(frozen=True)
class _ExactEurResidual:
    kind: _ProjectionKind
    amount: Decimal


@dataclass(frozen=True)
class _ProjectedEvent:
    event_origin: EventOrigin
    timestamp: datetime
    non_fee_buckets: tuple[_ProjectedBucket, ...]
    fee_buckets: tuple[_ProjectedBucket, ...]
    exact_eur: _ExactEurResidual | None

    @property
    def all_buckets(self) -> tuple[_ProjectedBucket, ...]:
        return self.non_fee_buckets + self.fee_buckets


@dataclass(frozen=True)
class _ValuedProjectedLeg:
    leg: LedgerLeg
    kind: _ProjectionKind
    quantity: Decimal
    value_total_eur: Decimal

    @property
    def rate_eur_per_unit(self) -> Decimal:
        return self.value_total_eur / self.quantity


@dataclass(frozen=True)
class _ValuedEvent:
    event_origin: EventOrigin
    timestamp: datetime
    valued_non_fee_legs: tuple[_ValuedProjectedLeg, ...]
    valued_fee_legs: tuple[_ValuedProjectedLeg, ...]
    solved_non_fee_rates_by_asset: dict[AssetId, Decimal]

    @property
    def all_valued_legs(self) -> tuple[_ValuedProjectedLeg, ...]:
        return self.valued_non_fee_legs + self.valued_fee_legs


@dataclass
class _LotBalance:
    lot: AcquisitionLot
    remaining_quantity: Decimal
