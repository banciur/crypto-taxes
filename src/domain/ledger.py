from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import NewType
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

ChainId = NewType("ChainId", str)
WalletAddress = NewType("WalletAddress", str)
AssetId = NewType("AssetId", str)
LedgerEventId = NewType("LedgerEventId", UUID)
LegId = NewType("LegId", UUID)
LotId = NewType("LotId", UUID)
DisposalId = NewType("DisposalId", UUID)
WalletId = NewType("WalletId", str)


class EventType(StrEnum):
    TRADE = "TRADE"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    TRANSFER = "TRANSFER"
    REWARD = "REWARD"


class EventLocation(StrEnum):
    ETHEREUM = "ETHEREUM"
    ARBITRUM = "ARBITRUM"
    BASE = "BASE"
    OPTIMISM = "OPTIMISM"
    KRAKEN = "KRAKEN"
    COINBASE = "COINBASE"
    BINANCE = "BINANCE"
    INTERNAL = "INTERNAL"


class EventOrigin(BaseModel):
    location: EventLocation
    external_id: str

    @model_validator(mode="after")
    def _validate_external_id(self) -> EventOrigin:
        if not self.external_id:
            raise ValueError("external_id must be non-empty")
        return self


class LedgerLeg(BaseModel):
    """A single leg within an event.

    Quantity sign convention:
    - Positive quantity indicates an asset/position increase.
    - Negative quantity indicates an asset/position decrease.
    """

    id: LegId = LegId(Field(default_factory=uuid4))
    asset_id: AssetId
    quantity: Decimal
    wallet_id: WalletId
    is_fee: bool = False

    @model_validator(mode="after")
    def _validate_quantity(self) -> LedgerLeg:
        # Zero-quantity legs are not meaningful in the ledger.
        if self.quantity == 0:
            raise ValueError("LedgerLeg.quantity must be non-zero")
        return self


class LedgerEvent(BaseModel):
    id: LedgerEventId = LedgerEventId(Field(default_factory=uuid4))
    timestamp: datetime

    origin: EventOrigin
    ingestion: str
    event_type: EventType
    legs: list[LedgerLeg]

    @model_validator(mode="after")
    def _validate_fields(self) -> LedgerEvent:
        if not self.legs:
            raise ValueError("LedgerEvent must have at least one leg")
        if not self.ingestion:
            raise ValueError("LedgerEvent.ingestion must be non-empty")
        return self


class AcquisitionLot(BaseModel):
    id: LotId = LotId(Field(default_factory=uuid4))
    acquired_leg_id: LegId
    cost_per_unit: Decimal

    @model_validator(mode="after")
    def _validate_fields(self) -> AcquisitionLot:
        if self.cost_per_unit < 0:
            raise ValueError("cost_per_unit must be >= 0")
        return self


class DisposalLink(BaseModel):
    id: DisposalId = DisposalId(Field(default_factory=uuid4))
    disposal_leg_id: LegId
    lot_id: LotId
    quantity_used: Decimal
    proceeds_total: Decimal

    @model_validator(mode="after")
    def _validate(self) -> DisposalLink:
        if self.quantity_used <= 0:
            raise ValueError("quantity_used must be > 0")
        if self.proceeds_total < 0:
            raise ValueError("proceeds_total must be >= 0")
        return self
