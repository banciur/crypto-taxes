from collections.abc import Callable

from fastapi.testclient import TestClient

from domain.ledger import LedgerEvent
from tests.api.conftest import raw_event


def test_get_raw_events_includes_note(
    client: TestClient,
    persist_raw_events: Callable[[list[LedgerEvent]], None],
) -> None:
    note = "approve"
    persist_raw_events(
        [
            raw_event(
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
                note=note,
            )
        ]
    )

    response = client.get("/corrected-events")

    assert response.status_code == 200
    assert response.json()[0]["note"] == note
