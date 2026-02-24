from __future__ import annotations

from domain.correction import Spam
from domain.ledger import LedgerEvent


def apply_spam_corrections(*, raw_events: list[LedgerEvent], spam_markers: list[Spam]) -> list[LedgerEvent]:
    spam_origins = {(marker.event_origin.location.value, marker.event_origin.external_id) for marker in spam_markers}
    return [
        event for event in raw_events if (event.origin.location.value, event.origin.external_id) not in spam_origins
    ]
