from datetime import datetime
from typing import Any, NewType, Self, cast
from uuid import UUID, uuid4

from pydantic import Field, ValidationInfo, field_validator, model_validator

from domain.ledger import EventOrigin, LedgerLeg
from domain.validation import reject_duplicate_items, reject_internal_origins
from pydantic_base import StrictBaseModel

CorrectionId = NewType("CorrectionId", UUID)


class LedgerCorrectionDraft(StrictBaseModel):
    timestamp: datetime
    sources: frozenset[EventOrigin] = Field(default_factory=frozenset)
    legs: frozenset[LedgerLeg] = Field(default_factory=frozenset)
    note: str | None = None

    @field_validator("sources", "legs", mode="before")
    @classmethod
    def reject_duplicates(cls, value: Any, info: ValidationInfo) -> Any:
        # For bound field validator info.field_name is never None
        field_name = cast(str, info.field_name)
        item_model = EventOrigin if field_name == "sources" else LedgerLeg
        return reject_duplicate_items(value, item_model=item_model, field_name=field_name)

    @model_validator(mode="after")
    def _validate_shape(self) -> Self:
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
            return self

        reject_internal_origins(self.sources)
        return self


class LedgerCorrection(LedgerCorrectionDraft):
    id: CorrectionId = CorrectionId(Field(default_factory=uuid4))
