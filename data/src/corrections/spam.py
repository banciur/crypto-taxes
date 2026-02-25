from __future__ import annotations

from typing import Iterable, Iterator

from domain.correction import Spam
from domain.ledger import LedgerEvent


def apply_spam_corrections(*, raw_events: Iterable[LedgerEvent], spam_markers: Iterable[Spam]) -> Iterator[LedgerEvent]:
    spam_origins = {(marker.event_origin.location.value, marker.event_origin.external_id) for marker in spam_markers}
    return filter(lambda e: (e.origin.location.value, e.origin.external_id) not in spam_origins, raw_events)
