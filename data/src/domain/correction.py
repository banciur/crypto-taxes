from __future__ import annotations

from abc import ABC
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
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


class SpamCorrectionSource(StrEnum):
    MANUAL = "MANUAL"
    AUTO_MORALIS = "AUTO_MORALIS"


class Spam(Marker):
    source: SpamCorrectionSource = SpamCorrectionSource.MANUAL
    deleted_at: datetime | None = None


class AlreadyTaxed(Marker):
    pass


class SeedEvent(Correction, AbstractEvent):
    price_per_token: Decimal = Decimal("0")


class LinkMarker(Correction, AbstractEvent):
    event_origins: list[EventOrigin]
