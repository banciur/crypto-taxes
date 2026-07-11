from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal

from errors import CryptoTaxesError

from ..correction import LedgerCorrection
from ..ledger import AssetId, EventOrigin, LedgerEvent
from ..price_override import PriceOverride


class PriceOverrideResolutionError(CryptoTaxesError):
    """Raised when one or more price overrides do not match exactly one priceable corrected event."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("Price overrides could not be resolved:\n" + "\n".join(problems))


def build_override_rates_by_event_origin(
    corrected_events: Iterable[LedgerEvent],
    corrections: Iterable[LedgerCorrection],
    overrides: Iterable[PriceOverride],
) -> dict[EventOrigin, dict[AssetId, Decimal]]:
    """Map each override onto the event whose source set it exactly matches.

    A corrected event is identified by its source set: a raw event (no correction) by its own
    origin, a replacement's synthetic event by the raw origins. Ensures that each override matches
    exactly one event.
    """
    event_by_sources = _index_events_by_sources(corrected_events, corrections)

    resolved: dict[EventOrigin, dict[AssetId, Decimal]] = defaultdict(dict)
    problems: list[str] = []

    for override in overrides:
        event = event_by_sources.get(override.sources)
        if event is None:
            problems.append(_problem(override, "sources do not match any corrected event"))
            continue
        if override.asset_id not in {leg.asset_id for leg in event.legs}:
            problems.append(_problem(override, f"asset is not present in resolved event {_origin(event.event_origin)}"))
            continue

        priced_assets = resolved[event.event_origin]
        if override.asset_id in priced_assets:
            problems.append(
                _problem(override, f"conflicts with another override on event {_origin(event.event_origin)}")
            )
            continue
        priced_assets[override.asset_id] = override.rate_eur

    if problems:
        raise PriceOverrideResolutionError(problems)
    return dict(resolved)


def _index_events_by_sources(
    corrected_events: Iterable[LedgerEvent],
    corrections: Iterable[LedgerCorrection],
) -> dict[frozenset[EventOrigin], LedgerEvent]:
    replacement_sources_by_synthetic_origin = {
        cor.synthetic_event_origin: cor.sources
        for cor in corrections
        # The filter selects replacements only: `sources` drops opening balances (no sources), and
        # `legs` drops discards -- a discard emits no synthetic event (only corrections with legs do),
        # so there would be no corrected event for its sources to key.
        if cor.sources and cor.legs
    }

    return {
        replacement_sources_by_synthetic_origin.get(event.event_origin, frozenset({event.event_origin})): event
        for event in corrected_events
    }


def _problem(override: PriceOverride, reason: str) -> str:
    return f"Price override {override.id} (asset {override.asset_id}) {reason}."


def _origin(origin: EventOrigin) -> str:
    return f"{origin.location.value}/{origin.external_id}"
