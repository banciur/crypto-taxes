from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..ledger import AccountChainId, AssetId
from .models import AcquisitionLot


@dataclass(frozen=True)
class _ProjectedLeg:
    account_chain_id: AccountChainId
    quantity: Decimal


@dataclass(frozen=True)
class _ProjectedBucket:
    asset_id: AssetId
    is_fee: bool
    legs: tuple[_ProjectedLeg, ...]


@dataclass(frozen=True)
class _ProjectedEvent:
    non_fee_buckets: tuple[_ProjectedBucket, ...]
    fee_buckets: tuple[_ProjectedBucket, ...]
    exact_base_currency: Decimal | None

    @property
    def all_buckets(self) -> tuple[_ProjectedBucket, ...]:
        return self.non_fee_buckets + self.fee_buckets


@dataclass
class _LotBalance:
    lot: AcquisitionLot
    remaining_quantity: Decimal
