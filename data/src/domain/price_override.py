from decimal import Decimal
from typing import Any, NewType, Self
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from domain.ledger import AssetId, EventOrigin
from domain.validation import reject_duplicate_items, reject_internal_origins
from pydantic_base import StrictBaseModel

PriceOverrideId = NewType("PriceOverrideId", UUID)


class PriceOverrideDraft(StrictBaseModel):
    """A manual EUR per-unit rate for one asset in one corrected event.

    Identity is the set of raw source ``EventOrigin``s of the economic transaction being priced,
    so the override follows that transaction across the corrections boundary (e.g. after a raw
    event is later folded into a replacement correction). ``rate_eur`` is the EUR value of one unit
    of ``asset_id`` -- exactly what ``PriceProvider.rate(asset_id, EUR, ts)`` would return.
    """

    sources: frozenset[EventOrigin]
    asset_id: AssetId
    rate_eur: Decimal
    note: str | None = None

    @field_validator("sources", mode="before")
    @classmethod
    def _reject_duplicate_sources(cls, value: Any) -> Any:
        return reject_duplicate_items(value, item_model=EventOrigin, field_name="sources")

    @field_validator("asset_id")
    @classmethod
    def _normalize_asset_id(cls, value: str) -> AssetId:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("PriceOverride.asset_id must not be empty")
        return AssetId(normalized)

    @field_validator("rate_eur")
    @classmethod
    def _validate_rate_eur(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("PriceOverride.rate_eur must be positive")
        return value

    @model_validator(mode="after")
    def _validate_sources(self) -> Self:
        if len(self.sources) == 0:
            raise ValueError("PriceOverride requires at least one source")
        reject_internal_origins(self.sources)
        return self


class PriceOverride(PriceOverrideDraft):
    id: PriceOverrideId = PriceOverrideId(Field(default_factory=uuid4))
