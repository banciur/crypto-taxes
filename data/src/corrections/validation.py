from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from domain.correction import LedgerCorrection
from domain.ledger import LedgerEvent


class CorrectionValidationError(Exception):
    pass


def validate_ingestion_corrections(
    *,
    raw_events: Iterable[LedgerEvent],
    corrections: Iterable[LedgerCorrection],
) -> None:
    raw_event_counts = Counter(
        (event.event_origin.location.value, event.event_origin.external_id) for event in raw_events
    )
    correction_source_counts = Counter(
        (source.location.value, source.external_id) for correction in corrections for source in correction.sources
    )

    missing_or_ambiguous_sources = [
        origin_key
        for origin_key, source_count in correction_source_counts.items()
        if source_count > 0 and raw_event_counts[origin_key] != 1
    ]
    if missing_or_ambiguous_sources:
        formatted_origins = ", ".join(
            _format_origin_key(origin_key) for origin_key in sorted(missing_or_ambiguous_sources)
        )
        raise CorrectionValidationError(f"Correction source must match exactly one raw event: {formatted_origins}")

    duplicate_correction_sources = [
        origin_key for origin_key, source_count in correction_source_counts.items() if source_count > 1
    ]
    if duplicate_correction_sources:
        formatted_origins = ", ".join(
            _format_origin_key(origin_key) for origin_key in sorted(duplicate_correction_sources)
        )
        raise CorrectionValidationError(
            f"Raw event cannot be consumed by more than one correction source: {formatted_origins}"
        )


def _format_origin_key(origin_key: tuple[str, str]) -> str:
    location, external_id = origin_key
    return f"{location}/{external_id}"
