from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from domain.ledger import AssetId, EventLocation, EventOrigin, LedgerEvent, LedgerLeg

BASE_TIMESTAMP = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
EXOTIC = AssetId("EXOTIC")


def make_event(
    *,
    external_id: str | None = None,
    legs: list[LedgerLeg],
    offset_days: int = 0,
    timestamp: datetime | None = None,
) -> LedgerEvent:
    event_timestamp = timestamp or (BASE_TIMESTAMP + timedelta(days=offset_days))
    return LedgerEvent(
        timestamp=event_timestamp,
        event_origin=EventOrigin(location=EventLocation.INTERNAL, external_id=external_id or str(uuid4())),
        ingestion="test",
        legs=legs,
    )


__all__ = ["BASE_TIMESTAMP", "EXOTIC", "make_event"]
