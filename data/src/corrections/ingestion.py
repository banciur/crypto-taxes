# This file is completely vibed and I didn't read it.
from corrections.validation import validate_ingestion_corrections
from domain.correction import LedgerCorrection
from domain.ledger import EventLocation, EventOrigin, LedgerEvent

LEDGER_CORRECTION_INGESTION = "ledger_correction"


def ledger_event_from_correction(correction: LedgerCorrection) -> LedgerEvent:
    if len(correction.legs) == 0:
        raise ValueError("Cannot build LedgerEvent from correction without legs")

    return LedgerEvent(
        timestamp=correction.timestamp,
        event_origin=EventOrigin(
            location=EventLocation.INTERNAL,
            external_id=str(correction.id),
        ),
        ingestion=LEDGER_CORRECTION_INGESTION,
        note=correction.note,
        legs=list(correction.legs),
    )


def apply_ingestion_corrections(
    *,
    raw_events: list[LedgerEvent],
    corrections: list[LedgerCorrection],
) -> list[LedgerEvent]:
    validate_ingestion_corrections(
        raw_events=raw_events,
        corrections=corrections,
    )
    claimed_source_keys = {
        (source.location.value, source.external_id) for correction in corrections for source in correction.sources
    }
    corrected_events = [
        event
        for event in raw_events
        if (event.event_origin.location.value, event.event_origin.external_id) not in claimed_source_keys
    ]
    corrected_events.extend(
        ledger_event_from_correction(correction) for correction in corrections if len(correction.legs) > 0
    )
    corrected_events.sort(
        key=lambda event: (
            event.timestamp,
            event.event_origin.location.value,
            event.event_origin.external_id,
        )
    )
    return corrected_events
