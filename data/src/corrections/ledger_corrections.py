from __future__ import annotations

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
        legs=list(correction.legs),
    )
