# This file is completely vibed.
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from domain.correction import Replacement, Spam
from domain.ledger import LedgerEvent


class CorrectionValidationError(Exception):
    pass


def validate_ingestion_corrections(
    *,
    raw_events: Iterable[LedgerEvent],
    spam_markers: Iterable[Spam],
    replacements: Iterable[Replacement],
) -> None:
    raw_event_counts = Counter(
        (event.event_origin.location.value, event.event_origin.external_id) for event in raw_events
    )
    replacement_source_counts = Counter(
        (source.location.value, source.external_id) for replacement in replacements for source in replacement.sources
    )
    spam_origins = {(marker.event_origin.location.value, marker.event_origin.external_id) for marker in spam_markers}

    missing_or_ambiguous_sources = [
        origin_key
        for origin_key, replacement_count in replacement_source_counts.items()
        if replacement_count > 0 and raw_event_counts[origin_key] != 1
    ]
    if missing_or_ambiguous_sources:
        formatted_origins = ", ".join(
            _format_origin_key(origin_key) for origin_key in sorted(missing_or_ambiguous_sources)
        )
        raise CorrectionValidationError(f"Replacement source must match exactly one raw event: {formatted_origins}")

    duplicate_replacement_sources = [
        origin_key for origin_key, replacement_count in replacement_source_counts.items() if replacement_count > 1
    ]
    if duplicate_replacement_sources:
        formatted_origins = ", ".join(
            _format_origin_key(origin_key) for origin_key in sorted(duplicate_replacement_sources)
        )
        raise CorrectionValidationError(
            f"Raw event cannot be consumed by more than one replacement source: {formatted_origins}"
        )

    spam_replacement_overlap = sorted(spam_origins & set(replacement_source_counts))
    if spam_replacement_overlap:
        formatted_origins = ", ".join(_format_origin_key(origin_key) for origin_key in spam_replacement_overlap)
        raise CorrectionValidationError(f"Raw event cannot be both spam and replacement source: {formatted_origins}")


def _format_origin_key(origin_key: tuple[str, str]) -> str:
    location, external_id = origin_key
    return f"{location}/{external_id}"
