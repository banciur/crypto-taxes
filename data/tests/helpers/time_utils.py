from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import count
from random import Random
from typing import Callable, Iterable

from domain.ledger import EventLocation, EventOrigin, EventType, LedgerEvent, LedgerLeg


@dataclass
class TimeGenerator:
    """Deterministic timestamp generator with random-ish gaps."""

    _current: datetime | None = None
    _rng: Random = Random(0)
    _seed: int = 0

    def __call__(self) -> datetime:
        return self.next()

    def next(self) -> datetime:
        if self._current is None:
            self._current = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self._current += timedelta(seconds=self._rng.randint(5, 60))
        return self._current

    def reset(self) -> None:
        self._current = None
        self._rng = Random(self._seed)


DEFAULT_TIME_GEN = TimeGenerator()
_EVENT_COUNTER = count()


def make_event(
    *,
    event_type: EventType,
    legs: Iterable[LedgerLeg],
    timestamp: datetime | None = None,
    ts_gen: Callable[[], datetime] | None = None,
    origin: EventOrigin | None = None,
    ingestion: str = "test",
) -> LedgerEvent:
    """Helper to create a LedgerEvent with an auto-generated timestamp."""
    if timestamp is None:
        if ts_gen is None:
            ts_gen = DEFAULT_TIME_GEN
        timestamp = ts_gen()

    if origin is None:
        origin = EventOrigin(location=EventLocation.INTERNAL, external_id=f"test-event-{next(_EVENT_COUNTER)}")

    return LedgerEvent(
        timestamp=timestamp,
        origin=origin,
        ingestion=ingestion,
        event_type=event_type,
        legs=list(legs),
    )
