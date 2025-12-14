from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import NewType
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from domain.base_types import AbstractEvent, EventOrigin, LegId

ChainId = NewType("ChainId", str)
WalletAddress = NewType("WalletAddress", str)

LedgerEventId = NewType("LedgerEventId", UUID)
LotId = NewType("LotId", UUID)
DisposalId = NewType("DisposalId", UUID)


class EventType(StrEnum):
    TRADE = "TRADE"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    TRANSFER = "TRANSFER"
    REWARD = "REWARD"
    OPERATION = "OPERATION"


class LedgerEvent(AbstractEvent):
    id: LedgerEventId = LedgerEventId(Field(default_factory=uuid4))

    origin: EventOrigin
    ingestion: str
    event_type: EventType

    @model_validator(mode="after")
    def _validate_fields(self) -> LedgerEvent:
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
