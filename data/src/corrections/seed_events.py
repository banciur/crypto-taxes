from __future__ import annotations

from domain.correction import SeedEvent
from domain.ledger import LedgerEvent
from importers.seed_events import ledger_events_from_seed_events


def apply_seed_event_corrections(*, raw_events: list[LedgerEvent], seed_events: list[SeedEvent]) -> list[LedgerEvent]:
    seed_ledger_events = ledger_events_from_seed_events(seed_events)
    corrected = [*raw_events, *seed_ledger_events]
    corrected.sort(key=lambda e: (e.timestamp, e.origin.location.value, e.origin.external_id, e.ingestion))
    return corrected
