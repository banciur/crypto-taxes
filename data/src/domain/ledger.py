from __future__ import annotations

from abc import ABC
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, NewType
from uuid import UUID, uuid4

from pydantic import Field, StringConstraints, field_validator

from pydantic_base import StrictBaseModel

AssetId = NewType("AssetId", str)
DisposalId = NewType("DisposalId", UUID)
LedgerEventId = NewType("LedgerEventId", UUID)
LegId = NewType("LegId", UUID)
LotId = NewType("LotId", UUID)
WalletAddress = NewType("WalletAddress", str)
AccountChainId = NewType("AccountChainId", str)


class EventLocation(StrEnum):
    ETHEREUM = "ETHEREUM"
    ARBITRUM = "ARBITRUM"
    BASE = "BASE"
    OPTIMISM = "OPTIMISM"
    KRAKEN = "KRAKEN"
    COINBASE = "COINBASE"
    BINANCE = "BINANCE"
    INTERNAL = "INTERNAL"


class EventOrigin(StrictBaseModel):
    location: EventLocation
    external_id: Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]


class LedgerLeg(StrictBaseModel):
    """A single leg within an event.

    Quantity sign convention:
    - Positive quantity indicates an asset/position increase.
    - Negative quantity indicates an asset/position decrease.
    """

    id: LegId = LegId(Field(default_factory=uuid4))
    asset_id: AssetId
    quantity: Decimal
    account_chain_id: AccountChainId
    is_fee: bool = False

    @field_validator("quantity")
    @classmethod
    def _validate_quantity(cls, value: Decimal) -> Decimal:
        if value == 0:
            raise ValueError("LedgerLeg.quantity must be non-zero")
        return value


class AbstractEvent(StrictBaseModel, ABC):
    timestamp: datetime
    legs: list[LedgerLeg] = Field(min_length=1)


class LedgerEvent(AbstractEvent):
    id: LedgerEventId = LedgerEventId(Field(default_factory=uuid4))

    event_origin: EventOrigin
    ingestion: Annotated[str, Field(min_length=1)]


class AcquisitionLot(StrictBaseModel):
    id: LotId = LotId(Field(default_factory=uuid4))
    acquired_leg_id: LegId
    cost_per_unit: Annotated[Decimal, Field(ge=0)]


class DisposalLink(StrictBaseModel):
    id: DisposalId = DisposalId(Field(default_factory=uuid4))
    disposal_leg_id: LegId
    lot_id: LotId
    quantity_used: Annotated[Decimal, Field(gt=0)]
    proceeds_total: Annotated[Decimal, Field(ge=0)]
