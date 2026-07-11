from collections.abc import Iterable
from decimal import Decimal
from typing import Annotated, NewType
from uuid import UUID, uuid4

from pydantic import Field

from domain.ledger import AssetId, EventOrigin, LedgerEvent
from errors import CryptoTaxesError
from pydantic_base import StrictBaseModel

PriceOverrideId = NewType("PriceOverrideId", UUID)


class PriceOverrideDraft(StrictBaseModel):
    event_origin: EventOrigin
    asset_id: AssetId
    rate_eur: Annotated[Decimal, Field(gt=0)]
    note: str | None = None


class PriceOverride(PriceOverrideDraft):
    id: PriceOverrideId = PriceOverrideId(Field(default_factory=uuid4))


class PriceOverrideValidationError(CryptoTaxesError):
    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("Invalid price overrides:\n" + "\n".join(problems))


def validate_overrides(
    corrected_events: Iterable[LedgerEvent],
    overrides: Iterable[PriceOverride],
) -> None:
    """Require every override to price an asset of the corrected event it targets.

    A corrected event's ``event_origin`` uniquely identifies it (passthrough origins are unique; a
    replacement's synthetic ``(INTERNAL, correction.id)`` origin is unique per correction), so an
    override matches by a plain lookup of its ``event_origin``. Aborts with a
    ``PriceOverrideValidationError`` listing every override that did not match.
    """
    event_by_origin = {event.event_origin: event for event in corrected_events}
    problems: list[str] = []

    for override in overrides:
        event = event_by_origin.get(override.event_origin)
        if event is None:
            problems.append(_problem(override, "does not match any corrected event"))
        elif override.asset_id not in {leg.asset_id for leg in event.legs}:
            problems.append(_problem(override, "prices an asset absent from the legs of its corrected event"))

    if problems:
        raise PriceOverrideValidationError(problems)


def _problem(override: PriceOverride, reason: str) -> str:
    return f"Price override {override.id} ({override.asset_id} @ {override.event_origin}) {reason}."
