from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from typing import TypedDict
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from accounts import KRAKEN_ACCOUNT_ID
from db.corrections_replacement import ReplacementCorrectionRepository
from domain.correction import Replacement
from domain.ledger import EventLocation, EventOrigin, LedgerEvent, LedgerLeg
from tests.api.conftest import raw_event
from tests.constants import BTC, ETH, LEDGER_WALLET


class ReplacementSourcePayload(TypedDict):
    location: str
    external_id: str


class ReplacementLegPayload(TypedDict):
    asset_id: str
    quantity: str
    account_chain_id: str
    is_fee: bool


class ReplacementPayload(TypedDict):
    timestamp: str
    sources: list[ReplacementSourcePayload]
    legs: list[ReplacementLegPayload]


def _replacement_payload(
    *,
    timestamp: str = "2024-02-03T10:30:00Z",
    sources: list[ReplacementSourcePayload] | None = None,
) -> ReplacementPayload:
    return {
        "timestamp": timestamp,
        "sources": sources or [ReplacementSourcePayload(location="ARBITRUM", external_id="0xabc")],
        "legs": [
            {
                "asset_id": BTC,
                "quantity": "-0.1",
                "account_chain_id": KRAKEN_ACCOUNT_ID,
                "is_fee": False,
            },
            {
                "asset_id": BTC,
                "quantity": "0.09995",
                "account_chain_id": LEDGER_WALLET,
                "is_fee": False,
            },
            {
                "asset_id": ETH,
                "quantity": "-0.001",
                "account_chain_id": KRAKEN_ACCOUNT_ID,
                "is_fee": True,
            },
        ],
    }


def test_post_creates_and_get_lists_replacement_corrections(
    client: TestClient,
    persist_raw_events: Callable[[list[LedgerEvent]], None],
) -> None:
    payload = _replacement_payload()
    source = payload["sources"][0]
    persist_raw_events(
        [
            raw_event(
                location=EventLocation(source["location"]),
                external_id=source["external_id"],
                timestamp=datetime(2024, 2, 3, 10, 0, tzinfo=timezone.utc),
            )
        ],
    )

    create_response = client.post("/replacement-corrections", json=payload)
    list_response = client.get("/replacement-corrections")

    assert create_response.status_code == 201
    created = create_response.json()
    assert set(created) == {"id", "timestamp", "sources", "legs"}
    assert created["timestamp"] == payload["timestamp"]
    assert created["sources"] == payload["sources"]
    assert all(leg["id"] for leg in created["legs"])

    assert list_response.status_code == 200
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]
    assert listed[0]["timestamp"] == created["timestamp"]
    assert listed[0]["sources"] == created["sources"]
    assert {leg["id"] for leg in listed[0]["legs"]} == {leg["id"] for leg in created["legs"]}


def test_get_lists_persisted_replacement_without_raw_lookup(
    client: TestClient,
    persist_replacement: Callable[[Replacement], None],
) -> None:
    replacement = Replacement(
        timestamp=datetime(2024, 2, 4, 12, 0, tzinfo=timezone.utc),
        sources=[EventOrigin(location=EventLocation.BASE, external_id="0xorphan")],
        legs=[
            LedgerLeg(asset_id=ETH, quantity=Decimal("1"), account_chain_id=LEDGER_WALLET),
        ],
    )
    persist_replacement(replacement)

    response = client.get("/replacement-corrections")

    assert response.status_code == 200
    listed = response.json()
    assert len(listed) == 1
    assert listed[0]["id"] == str(replacement.id)
    assert listed[0]["timestamp"] == "2024-02-04T12:00:00Z"
    assert listed[0]["sources"] == [{"location": "BASE", "external_id": "0xorphan"}]


def test_post_returns_409_when_source_is_missing_from_raw_events(client: TestClient) -> None:
    response = client.post("/replacement-corrections", json=_replacement_payload())

    assert response.status_code == 409
    assert response.json() == {"detail": "Replacement source must match exactly one raw event: ARBITRUM/0xabc"}


def test_post_returns_409_when_source_is_marked_as_spam(
    client: TestClient,
    persist_raw_events: Callable[[list[LedgerEvent]], None],
) -> None:
    payload = _replacement_payload()
    source = payload["sources"][0]
    persist_raw_events(
        [
            raw_event(
                location=EventLocation(source["location"]),
                external_id=source["external_id"],
                timestamp=datetime(2024, 2, 5, 9, 0, tzinfo=timezone.utc),
            )
        ],
    )
    spam_response = client.post("/spam-corrections", json=source)

    response = client.post("/replacement-corrections", json=payload)

    assert spam_response.status_code == 204
    assert response.status_code == 409
    assert response.json() == {"detail": "Raw event cannot be both spam and replacement source: ARBITRUM/0xabc"}


def test_post_returns_409_when_source_is_already_consumed_by_replacement(
    client: TestClient,
    persist_raw_events: Callable[[list[LedgerEvent]], None],
) -> None:
    payload = _replacement_payload()
    source = payload["sources"][0]
    persist_raw_events(
        [
            raw_event(
                location=EventLocation(source["location"]),
                external_id=source["external_id"],
                timestamp=datetime(2024, 2, 6, 9, 0, tzinfo=timezone.utc),
            )
        ],
    )
    initial_response = client.post("/replacement-corrections", json=payload)

    response = client.post("/replacement-corrections", json=payload)

    assert initial_response.status_code == 201
    assert response.status_code == 409
    assert response.json() == {
        "detail": "Raw event cannot be consumed by more than one replacement source: ARBITRUM/0xabc"
    }


def test_post_returns_409_when_repository_hits_source_uniqueness_race(
    client: TestClient,
    persist_raw_events: Callable[[list[LedgerEvent]], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _replacement_payload()
    source = payload["sources"][0]
    persist_raw_events(
        [
            raw_event(
                location=EventLocation(source["location"]),
                external_id=source["external_id"],
                timestamp=datetime(2024, 2, 7, 9, 0, tzinfo=timezone.utc),
            )
        ],
    )

    def raise_integrity_error(_: ReplacementCorrectionRepository, __: Replacement) -> Replacement:
        raise IntegrityError("insert", {}, Exception("duplicate source"))

    monkeypatch.setattr(ReplacementCorrectionRepository, "create", raise_integrity_error)

    response = client.post("/replacement-corrections", json=payload)

    assert response.status_code == 409
    assert response.json() == {"detail": "Replacement source is already consumed by another replacement"}


def test_delete_removes_record_by_correction_id(
    client: TestClient,
    persist_raw_events: Callable[[list[LedgerEvent]], None],
) -> None:
    payload = _replacement_payload()
    source = payload["sources"][0]
    persist_raw_events(
        [
            raw_event(
                location=EventLocation(source["location"]),
                external_id=source["external_id"],
                timestamp=datetime(2024, 2, 8, 9, 0, tzinfo=timezone.utc),
            )
        ],
    )
    created = client.post("/replacement-corrections", json=payload).json()

    delete_response = client.delete(f"/replacement-corrections/{created['id']}")

    assert delete_response.status_code == 204
    assert client.get("/replacement-corrections").json() == []


def test_delete_is_idempotent_for_missing_replacement(client: TestClient) -> None:
    response = client.delete(f"/replacement-corrections/{uuid4()}")

    assert response.status_code == 204
    assert client.get("/replacement-corrections").json() == []
