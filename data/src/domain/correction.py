from __future__ import annotations

from abc import ABC
from typing import NewType
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from domain.base_types import AbstractEvent
from domain.ledger import EventOrigin, EventType

CorrectionId = NewType("CorrectionId", UUID)


class Correction(BaseModel, ABC):
    id: CorrectionId = CorrectionId(Field(default_factory=uuid4))


class Marker(Correction, ABC):
    event_origin: EventOrigin


class Spam(Marker):
    pass

class AlreadyTaxed(Marker):
    pass

class SeedMarker(Correction, AbstractEvent):
    pass

class LinkMarker(Correction, AbstractEvent):
    event_origins: list[EventOrigin]
    event_type: EventType
