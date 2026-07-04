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
class _ProjectedAssetResidualGroup:
    asset_id: AssetId
    residuals: Sequence[_ProjectedResidualLeg]


@dataclass(frozen=True)
class _ProjectedEvent:
    non_fee_groups: Sequence[_ProjectedAssetResidualGroup]
    fee_groups: Sequence[_ProjectedAssetResidualGroup]


@dataclass
class _LotBalance:
    lot: AcquisitionLot
    remaining_quantity: Decimal
