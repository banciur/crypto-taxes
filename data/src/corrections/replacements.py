from __future__ import annotations

from collections.abc import Iterable, Iterator
from itertools import chain

from domain.correction import Replacement
from domain.ledger import EventLocation, EventOrigin, LedgerEvent

REPLACEMENT_CORRECTION_INGESTION = "replacement_correction"


def apply_replacement_corrections(
    *,
    raw_events: Iterable[LedgerEvent],
    replacements: Iterable[Replacement],
) -> Iterator[LedgerEvent]:
    replacements_list = list(replacements)
    replacement_sources = {
        (source.location.value, source.external_id)
        for replacement in replacements_list
        for source in replacement.sources
    }
    kept_raw_events = [
        event
        for event in raw_events
        if (event.event_origin.location.value, event.event_origin.external_id) not in replacement_sources
    ]
    replacement_events = [_ledger_event_from_replacement(replacement) for replacement in replacements_list]
    return chain(kept_raw_events, replacement_events)


def _ledger_event_from_replacement(replacement: Replacement) -> LedgerEvent:
    return LedgerEvent(
        timestamp=replacement.timestamp,
        event_origin=EventOrigin(
            location=EventLocation.INTERNAL,
            external_id=f"replacement:{replacement.id}",
        ),
        ingestion=REPLACEMENT_CORRECTION_INGESTION,
        legs=list(replacement.legs),
    )
