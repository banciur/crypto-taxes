# This file is completely vibed.
from __future__ import annotations

from corrections.replacements import apply_replacement_corrections
from corrections.seed_events import apply_seed_event_corrections
from corrections.spam import apply_spam_corrections
from corrections.validation import validate_ingestion_corrections
from domain.correction import Replacement, SeedEvent, Spam
from domain.ledger import LedgerEvent


def apply_ingestion_corrections(
    *,
    raw_events: list[LedgerEvent],
    spam_markers: list[Spam],
    replacements: list[Replacement],
    seed_events: list[SeedEvent],
) -> list[LedgerEvent]:
    validate_ingestion_corrections(
        raw_events=raw_events,
        spam_markers=spam_markers,
        replacements=replacements,
    )
    spam_filtered_events = list(
        apply_spam_corrections(
            raw_events=raw_events,
            spam_markers=spam_markers,
        )
    )
    replacement_corrected_events = list(
        apply_replacement_corrections(
            raw_events=spam_filtered_events,
            replacements=replacements,
        )
    )
    corrected_events = apply_seed_event_corrections(
        raw_events=replacement_corrected_events,
        seed_events=seed_events,
    )
    corrected_events.sort(
        key=lambda event: (
            event.timestamp,
            event.event_origin.location.value,
            event.event_origin.external_id,
            event.ingestion,
        )
    )
    return corrected_events
