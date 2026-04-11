from __future__ import annotations

from collections.abc import Sequence
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
    legs: Sequence[_ProjectedResidualLeg]


@dataclass(frozen=True)
class _ProjectedEvent:
    non_fee_groups: Sequence[_ProjectedAssetGroup]
    fee_groups: Sequence[_ProjectedAssetGroup]

    @property
    def all_groups(self) -> Sequence[_ProjectedAssetGroup]:
        return [*self.non_fee_groups, *self.fee_groups]


@dataclass
class _LotBalance:
    lot: AcquisitionLot
    remaining_quantity: Decimal
