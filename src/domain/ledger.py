from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class EventType(StrEnum):
    TRADE = "TRADE"


class LedgerLeg(BaseModel):
    """A single leg within an event.

    Quantity sign convention:
    - Positive quantity indicates an asset/position increase.
    - Negative quantity indicates an asset/position decrease.
    """

    id: UUID = Field(default_factory=uuid4)
    asset_id: str
    quantity: Decimal
    wallet_id: str
    is_fee: bool = False

    @model_validator(mode="after")
    def _validate_quantity(self) -> "LedgerLeg":
        # Zero-quantity legs are not meaningful in the ledger.
        if self.quantity == 0:
            raise ValueError("LedgerLeg.quantity must be non-zero")
        return self


class LedgerEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime

    event_type: EventType
    legs: list[LedgerLeg]

    @model_validator(mode="after")
    def _validate_legs(self) -> "LedgerEvent":
        if not self.legs:
            raise ValueError("LedgerEvent must have at least one leg")
        return self


class AcquisitionLot(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    acquired_event_id: UUID
    acquired_leg_id: UUID
    cost_eur_per_unit: Decimal

    @model_validator(mode="after")
    def _validate_fields(self) -> "AcquisitionLot":
        if self.cost_eur_per_unit < 0:
            raise ValueError("cost_eur_per_unit must be >= 0")
        return self


class DisposalLink(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    disposal_leg_id: UUID
    lot_id: UUID
    quantity_used: Decimal
    proceeds_total_eur: Decimal

    @model_validator(mode="after")
    def _validate(self) -> "DisposalLink":
        if self.quantity_used <= 0:
            raise ValueError("quantity_used must be > 0")
        if self.proceeds_total_eur < 0:
            raise ValueError("proceeds_total_eur must be >= 0")
        return self


__all__ = [
    "EventType",
    "LedgerLeg",
    "LedgerEvent",
    "AcquisitionLot",
    "DisposalLink",
]
