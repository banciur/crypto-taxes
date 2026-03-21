from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import NewType
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from domain.ledger import EventLocation, EventOrigin, LedgerLeg
from pydantic_base import StrictBaseModel

CorrectionId = NewType("CorrectionId", UUID)


class LedgerCorrection(StrictBaseModel):
    id: CorrectionId = CorrectionId(Field(default_factory=uuid4))
    timestamp: datetime
    sources: list[EventOrigin] = Field(default_factory=list)
    legs: list[LedgerLeg] = Field(default_factory=list)
    price_per_token: Decimal | None = None
    note: str = ""

    @model_validator(mode="after")
    def _validate_shape(self) -> LedgerCorrection:
        if len(self.sources) == 0 and len(self.legs) == 0:
            raise ValueError("LedgerCorrection requires sources or legs")

        if len(self.sources) == 0:
            if len(self.legs) != 1:
                raise ValueError("Source-less LedgerCorrection requires exactly one leg")
            leg = self.legs[0]
            if leg.quantity <= 0:
                raise ValueError("Source-less LedgerCorrection leg must be positive")
            if leg.is_fee:
                raise ValueError("Source-less LedgerCorrection leg must not be a fee")
            if self.price_per_token is not None and self.price_per_token < 0:
                raise ValueError("Source-less LedgerCorrection.price_per_token must be >= 0")
            return self

        source_keys = {(source.location, source.external_id) for source in self.sources}
        if len(source_keys) != len(self.sources):
            raise ValueError("LedgerCorrection.sources must not contain duplicates")
        if any(source.location == EventLocation.INTERNAL for source in self.sources):
            raise ValueError("LedgerCorrection.sources must not contain INTERNAL origins")
        if self.price_per_token is not None:
            raise ValueError("Source-backed LedgerCorrection must not set price_per_token")
        return self

    @property
    def is_source_backed(self) -> bool:
        return len(self.sources) > 0

    @property
    def is_discard(self) -> bool:
        return self.is_source_backed and len(self.legs) == 0

    @property
    def is_replacement(self) -> bool:
        return self.is_source_backed and len(self.legs) > 0

    @property
    def is_opening_balance(self) -> bool:
        return not self.is_source_backed
