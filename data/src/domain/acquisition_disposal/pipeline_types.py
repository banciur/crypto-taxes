from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..ledger import AccountChainId, AssetId
from .models import AcquisitionLot


@dataclass(frozen=True)
class _ProjectedResidualLeg:
    account_chain_id: AccountChainId
    quantity: Decimal


@dataclass(frozen=True)
class _ProjectedAssetGroup:
    asset_id: AssetId
    is_fee: bool
    legs: tuple[_ProjectedResidualLeg, ...]


@dataclass(frozen=True)
class _ProjectedEvent:
    non_fee_buckets: tuple[_ProjectedAssetGroup, ...]
    fee_buckets: tuple[_ProjectedAssetGroup, ...]
    exact_base_currency: Decimal | None

    @property
    def all_buckets(self) -> tuple[_ProjectedAssetGroup, ...]:
        return self.non_fee_buckets + self.fee_buckets


@dataclass
class _LotBalance:
    lot: AcquisitionLot
    remaining_quantity: Decimal
