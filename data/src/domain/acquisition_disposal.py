from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import uuid4

from pydantic import Field

from pydantic_base import StrictBaseModel

from .ledger import AccountChainId, AssetId, DisposalId, EventOrigin, LotId


class AcquisitionLot(StrictBaseModel):
    id: LotId = LotId(Field(default_factory=uuid4))
    event_origin: EventOrigin
    account_chain_id: AccountChainId
    asset_id: AssetId
    is_fee: bool
    timestamp: datetime
    quantity_acquired: Annotated[Decimal, Field(gt=0)]
    cost_per_unit: Annotated[Decimal, Field(ge=0)]


class DisposalLink(StrictBaseModel):
    id: DisposalId = DisposalId(Field(default_factory=uuid4))
    lot_id: LotId
    event_origin: EventOrigin
    account_chain_id: AccountChainId
    asset_id: AssetId
    is_fee: bool
    timestamp: datetime
    quantity_used: Annotated[Decimal, Field(gt=0)]
    proceeds_total: Annotated[Decimal, Field(ge=0)]
