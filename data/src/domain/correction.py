from __future__ import annotations

from abc import ABC
from decimal import Decimal
from typing import NewType
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from domain.ledger import AbstractEvent, EventOrigin, EventType

CorrectionId = NewType("CorrectionId", UUID)


class Correction(BaseModel, ABC):
    id: CorrectionId = CorrectionId(Field(default_factory=uuid4))


class Marker(Correction, ABC):
    event_origin: EventOrigin


class Spam(Marker):
    pass


class AlreadyTaxed(Marker):
    pass


class SeedEvent(Correction, AbstractEvent):
    price_per_token: Decimal = Decimal("0")


class LinkMarker(Correction, AbstractEvent):
    event_origins: list[EventOrigin]
    event_type: EventType
