from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, NewType
from uuid import UUID, uuid4

from pydantic import Field, ValidationInfo, field_validator, model_validator

from domain.ledger import EventLocation, EventOrigin, LedgerLeg
from pydantic_base import StrictBaseModel

CorrectionId = NewType("CorrectionId", UUID)


class LedgerCorrection(StrictBaseModel):
    id: CorrectionId = CorrectionId(Field(default_factory=uuid4))
    timestamp: datetime
    sources: frozenset[EventOrigin] = Field(default_factory=frozenset)
    legs: frozenset[LedgerLeg] = Field(default_factory=frozenset)
    price_per_token: Decimal | None = None
    note: str | None = None

    @field_validator("sources", "legs", mode="before")
    @classmethod
    def reject_duplicates(cls, value: Any, info: ValidationInfo) -> Any:
        if not isinstance(value, (list, tuple, set, frozenset)):
            return value

        normalized_items: list[StrictBaseModel]
        if info.field_name == "sources":
            normalized_items = [EventOrigin.model_validate(item) for item in value]
        elif info.field_name == "legs":
            normalized_items = [LedgerLeg.model_validate(item) for item in value]
        else:
            raise ValueError(f"Unsupported duplicate validation field: {info.field_name}")

        if len(normalized_items) != len(set(normalized_items)):
            raise ValueError(f"{info.field_name} must not contain duplicates")

        return value

    @model_validator(mode="after")
    def _validate_shape(self) -> LedgerCorrection:
        if len(self.sources) == 0 and len(self.legs) == 0:
            raise ValueError("LedgerCorrection requires sources or legs")

        if len(self.sources) == 0:
            if len(self.legs) != 1:
                raise ValueError("Source-less LedgerCorrection requires exactly one leg")
            leg = next(iter(self.legs))
            if leg.quantity <= 0:
                raise ValueError("Source-less LedgerCorrection leg must be positive")
            if leg.is_fee:
                raise ValueError("Source-less LedgerCorrection leg must not be a fee")
            if self.price_per_token is not None and self.price_per_token < 0:
                raise ValueError("Source-less LedgerCorrection.price_per_token must be >= 0")
            return self

        if any(source.location == EventLocation.INTERNAL for source in self.sources):
            raise ValueError("LedgerCorrection.sources must not contain INTERNAL origins")
        if self.price_per_token is not None:
            raise ValueError("Source-backed LedgerCorrection must not set price_per_token")
        return self
