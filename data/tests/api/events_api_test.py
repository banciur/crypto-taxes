from collections.abc import Callable
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from domain.ledger import EventLocation, LedgerEvent
from tests.api.conftest import raw_event


def test_get_raw_events_includes_note(
    client: TestClient,
    persist_raw_events: Callable[[list[LedgerEvent]], None],
) -> None:
    note = "approve"
    persist_raw_events(
        [
            raw_event(
                location=EventLocation.BASE,
                external_id="0xraw-note",
                timestamp=datetime(2024, 2, 3, 10, 0, tzinfo=timezone.utc),
                note=note,
            )
        ]
    )

    response = client.get("/raw-events")

    assert response.status_code == 200
    assert response.json()[0]["note"] == note


def test_get_corrected_events_includes_note(
    client: TestClient,
    persist_corrected_events: Callable[[list[LedgerEvent]], None],
) -> None:
    note = "depositAll"
    persist_corrected_events(
        [
            raw_event(
                location=EventLocation.OPTIMISM,
                external_id="0xcorrected-note",
                timestamp=datetime(2024, 2, 3, 10, 0, tzinfo=timezone.utc),
                note=note,
            )
        ]
    )

    response = client.get("/corrected-events")

    assert response.status_code == 200
    assert response.json()[0]["note"] == note
