from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from domain.ledger import EventLocation, LedgerEvent
from tests.api.conftest import raw_event


def _payload(*, location: str = "ARBITRUM", external_id: str = "0xabc") -> dict[str, str]:
    return {"location": location, "external_id": external_id}


def test_post_creates_and_get_lists_active_spam_corrections(
    client: TestClient,
    persist_raw_events: Callable[[list[LedgerEvent]], None],
) -> None:
    payload = _payload()
    timestamp = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    persist_raw_events(
        [
            raw_event(
                location=EventLocation(payload["location"]),
                external_id=payload["external_id"],
                timestamp=timestamp,
            )
        ],
    )

    create_response = client.post("/spam-corrections", json=payload)
    list_response = client.get("/spam-corrections")

    assert create_response.status_code == 204
    assert create_response.content == b""

    assert list_response.status_code == 200
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["event_origin"] == payload
    assert listed[0]["timestamp"] == client.get("/raw-events").json()[0]["timestamp"]
    assert set(listed[0]) == {"id", "event_origin", "timestamp"}


def test_get_raw_events_exposes_event_origin_key(
    client: TestClient,
    persist_raw_events: Callable[[list[LedgerEvent]], None],
) -> None:
    payload = _payload(external_id="0xshape")
    persist_raw_events(
        [
            raw_event(
                location=EventLocation(payload["location"]),
                external_id=payload["external_id"],
                timestamp=datetime(2024, 1, 1, 13, 0, tzinfo=timezone.utc),
            )
        ],
    )

    response = client.get("/raw-events")

    assert response.status_code == 200
    event = response.json()[0]
    assert event["event_origin"] == payload
    assert "origin" not in event


def test_get_lists_spam_corrections_in_raw_event_order_with_raw_timestamp(
    client: TestClient,
    persist_raw_events: Callable[[list[LedgerEvent]], None],
) -> None:
    first_payload = _payload(external_id="0xearly")
    second_payload = _payload(external_id="0xlate")
    first_timestamp = datetime(2024, 1, 2, 9, 0, tzinfo=timezone.utc)
    second_timestamp = datetime(2024, 1, 3, 9, 0, tzinfo=timezone.utc)
    persist_raw_events(
        [
            raw_event(
                location=EventLocation(second_payload["location"]),
                external_id=second_payload["external_id"],
                timestamp=second_timestamp,
            ),
            raw_event(
                location=EventLocation(first_payload["location"]),
                external_id=first_payload["external_id"],
                timestamp=first_timestamp,
            ),
        ],
    )

    client.post("/spam-corrections", json=second_payload)
    client.post("/spam-corrections", json=first_payload)

    raw_events = client.get("/raw-events").json()
    raw_timestamps_by_origin = {
        (event["event_origin"]["location"], event["event_origin"]["external_id"]): event["timestamp"]
        for event in raw_events
    }

    response = client.get("/spam-corrections")

    assert response.status_code == 200
    listed = response.json()
    assert [item["event_origin"] for item in listed] == [first_payload, second_payload]
    assert [item["timestamp"] for item in listed] == [
        raw_timestamps_by_origin[(first_payload["location"], first_payload["external_id"])],
        raw_timestamps_by_origin[(second_payload["location"], second_payload["external_id"])],
    ]


def test_delete_hides_record_and_post_restores_same_id(
    client: TestClient,
    persist_raw_events: Callable[[list[LedgerEvent]], None],
) -> None:
    payload = _payload(external_id="0xrestore")
    persist_raw_events(
        [
            raw_event(
                location=EventLocation(payload["location"]),
                external_id=payload["external_id"],
                timestamp=datetime(2024, 1, 4, 12, 0, tzinfo=timezone.utc),
            )
        ],
    )

    create_response = client.post("/spam-corrections", json=payload)
    created = client.get("/spam-corrections").json()[0]

    delete_response = client.request("DELETE", "/spam-corrections", json=payload)
    after_delete = client.get("/spam-corrections")
    restore_response = client.post("/spam-corrections", json=payload)
    restored = client.get("/spam-corrections").json()[0]

    assert create_response.status_code == 204
    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert after_delete.json() == []
    assert restore_response.status_code == 204
    assert restored["id"] == created["id"]


def test_duplicate_post_is_idempotent(
    client: TestClient,
    persist_raw_events: Callable[[list[LedgerEvent]], None],
) -> None:
    payload = _payload(external_id="0xdup")
    persist_raw_events(
        [
            raw_event(
                location=EventLocation(payload["location"]),
                external_id=payload["external_id"],
                timestamp=datetime(2024, 1, 5, 12, 0, tzinfo=timezone.utc),
            )
        ],
    )

    first_response = client.post("/spam-corrections", json=payload)
    first_listed = client.get("/spam-corrections").json()
    second_response = client.post("/spam-corrections", json=payload)

    listed = client.get("/spam-corrections").json()
    assert first_response.status_code == 204
    assert second_response.status_code == 204
    assert listed == first_listed


def test_delete_is_idempotent_for_missing_record(client: TestClient) -> None:
    response = client.request("DELETE", "/spam-corrections", json=_payload(external_id="0xmissing"))

    assert response.status_code == 204
    assert client.get("/spam-corrections").json() == []


def test_get_raises_when_spam_correction_has_no_matching_raw_event(client: TestClient) -> None:
    payload = _payload(external_id="0xorphan")
    response = client.post("/spam-corrections", json=payload)

    assert response.status_code == 204
    with pytest.raises(RuntimeError, match="Spam correction must match exactly one raw event"):
        client.get("/spam-corrections")


def test_invalid_event_origin_payload_returns_422(client: TestClient) -> None:
    response = client.post("/spam-corrections", json=_payload(location="NOT_A_CHAIN"))

    assert response.status_code == 422


def test_post_strips_whitespace_from_event_origin_external_id(
    client: TestClient,
    persist_raw_events: Callable[[list[LedgerEvent]], None],
) -> None:
    trimmed_external_id = "0xtrimmed"
    persist_raw_events(
        [
            raw_event(
                location=EventLocation.ARBITRUM,
                external_id=trimmed_external_id,
                timestamp=datetime(2024, 1, 6, 12, 0, tzinfo=timezone.utc),
            )
        ],
    )

    response = client.post(
        "/spam-corrections",
        json=_payload(external_id=f"  {trimmed_external_id}  "),
    )

    assert response.status_code == 204
    assert client.get("/spam-corrections").json()[0]["event_origin"] == _payload(external_id=trimmed_external_id)
