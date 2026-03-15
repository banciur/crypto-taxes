from __future__ import annotations

from abc import ABC
from collections.abc import Sequence
from decimal import Decimal
from typing import NewType
from uuid import UUID, uuid4

from pydantic import Field

from domain.ledger import AbstractEvent, EventOrigin
from pydantic_base import StrictBaseModel

CorrectionId = NewType("CorrectionId", UUID)


class Correction(StrictBaseModel, ABC):
    id: CorrectionId = CorrectionId(Field(default_factory=uuid4))


class Marker(Correction, ABC):
    event_origin: EventOrigin


class Spam(Marker):
    pass


class AlreadyTaxed(Marker):
    pass


class SeedEvent(Correction, AbstractEvent):
    price_per_token: Decimal = Decimal("0")


class Replacement(Correction, AbstractEvent):
    sources: Sequence[EventOrigin] = Field(min_length=1)
