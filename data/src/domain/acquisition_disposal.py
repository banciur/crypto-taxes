from __future__ import annotations

from abc import ABC
from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import uuid4

from pydantic import Field

from pydantic_base import StrictBaseModel

from .ledger import AccountChainId, AssetId, DisposalId, EventLegRef, EventOrigin, LegKey, LotId


class AbstractAcquisitionDisposal(StrictBaseModel, ABC):
    event_origin: EventOrigin
    account_chain_id: AccountChainId
    asset_id: AssetId
    is_fee: bool
    timestamp: datetime

    @property
    def leg_key(self) -> LegKey:
        return LegKey(
            account_chain_id=self.account_chain_id,
            asset_id=self.asset_id,
            is_fee=self.is_fee,
        )

    @property
    def source_leg_ref(self) -> EventLegRef:
        return EventLegRef(event_origin=self.event_origin, leg_key=self.leg_key)


class AcquisitionLot(AbstractAcquisitionDisposal):
    id: LotId = LotId(Field(default_factory=uuid4))
    quantity_acquired: Annotated[Decimal, Field(gt=0)]
    cost_per_unit: Annotated[Decimal, Field(ge=0)]


class DisposalLink(AbstractAcquisitionDisposal):
    id: DisposalId = DisposalId(Field(default_factory=uuid4))
    lot_id: LotId
    quantity_used: Annotated[Decimal, Field(gt=0)]
    proceeds_total: Annotated[Decimal, Field(ge=0)]
