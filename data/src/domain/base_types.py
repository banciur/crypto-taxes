from __future__ import annotations

from abc import ABC
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import NewType
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

LegId = NewType("LegId", UUID)
AssetId = NewType("AssetId", str)
WalletId = NewType("WalletId", str)


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


class AbstractEvent(BaseModel, ABC):
    timestamp: datetime

    legs: list[LedgerLeg]

    @model_validator(mode="after")
    def _validate_fields(self) -> AbstractEvent:
        if not self.legs:
            raise ValueError("Event must have at least one leg")
        return self
