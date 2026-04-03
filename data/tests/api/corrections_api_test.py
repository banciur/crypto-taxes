# TODO: Tests for corrections api were written quickly and do not cover most of the cases.
#  Please review and improve this file when making changes.

from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from typing import TypedDict
from uuid import uuid4

from fastapi.testclient import TestClient

from accounts import KRAKEN_ACCOUNT_ID
from domain.correction import LedgerCorrection, LedgerCorrectionDraft
from domain.ledger import EventLocation, EventOrigin, LedgerEvent, LedgerLeg
from tests.api.conftest import raw_event
from tests.constants import BTC, ETH, LEDGER_WALLET


class CorrectionSourcePayload(TypedDict):
    location: str
    external_id: str


class CorrectionLegPayload(TypedDict):
    asset_id: str
    quantity: str
    account_chain_id: str
    is_fee: bool


class CorrectionPayload(TypedDict, total=False):
    timestamp: str
    sources: list[CorrectionSourcePayload]
    legs: list[CorrectionLegPayload]
    note: str | None


def _replacement_payload(*, external_id: str = "0xabc") -> CorrectionPayload:
    return {
        "timestamp": "2024-02-03T10:30:00Z",
        "sources": [CorrectionSourcePayload(location="ARBITRUM", external_id=external_id)],
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
        "note": "replacement note",
    }


def _discard_payload(*, external_id: str = "0xspam") -> CorrectionPayload:
    return {
        "timestamp": "2024-02-03T10:00:00Z",
        "sources": [CorrectionSourcePayload(location="ARBITRUM", external_id=external_id)],
    }


def _opening_balance_payload() -> CorrectionPayload:
    return {
        "timestamp": "2024-02-01T00:00:00Z",
        "legs": [
            {
                "asset_id": BTC,
                "quantity": "1.5",
                "account_chain_id": LEDGER_WALLET,
                "is_fee": False,
            }
        ],
        "note": "opening balance",
    }


def test_post_creates_and_get_lists_discard(
    client: TestClient,
    persist_raw_events: Callable[[list[LedgerEvent]], None],
) -> None:
    payload = _discard_payload()
    persist_raw_events(
        [
            raw_event(
                location=EventLocation.ARBITRUM,
                external_id=payload["sources"][0]["external_id"],
                timestamp=datetime(2024, 2, 3, 10, 0, tzinfo=timezone.utc),
            )
        ],
    )

    create_response = client.post("/corrections", json=payload)
    list_response = client.get("/corrections")

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["timestamp"] == payload["timestamp"]
    assert created["sources"] == payload["sources"]
    assert created["legs"] == []
    assert "price_per_token" not in created
    assert "note" not in created

    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [created["id"]]


def test_post_creates_opening_balance(
    client: TestClient,
) -> None:
    response = client.post("/corrections", json=_opening_balance_payload())

    assert response.status_code == 201
    created = response.json()
    assert created["sources"] == []
    assert created["note"] == "opening balance"


def test_post_rejects_legacy_price_per_token_field(client: TestClient) -> None:
    response = client.post(
        "/corrections",
        json={
            **_opening_balance_payload(),
            "price_per_token": "123.45",
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert len(detail) == 1
    assert detail[0]["loc"][-1] == "price_per_token"
    assert detail[0]["type"] == "extra_forbidden"


def test_post_creates_replacement(
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

    response = client.post("/corrections", json=payload)

    assert response.status_code == 201
    created = response.json()
    assert created["timestamp"] == payload["timestamp"]
    assert created["sources"] == payload["sources"]
    assert len(created["legs"]) == 3
    assert created["note"] == "replacement note"


def test_post_returns_409_when_source_is_missing_from_raw_events(client: TestClient) -> None:
    response = client.post("/corrections", json=_discard_payload(external_id="0xmissing"))

    assert response.status_code == 409
    assert response.json() == {"detail": "Correction source must match exactly one raw event: ARBITRUM/0xmissing"}


def test_post_returns_409_when_source_is_already_consumed_by_active_correction(
    client: TestClient,
    persist_raw_events: Callable[[list[LedgerEvent]], None],
) -> None:
    payload = _discard_payload(external_id="0xdup")
    persist_raw_events(
        [
            raw_event(
                location=EventLocation.ARBITRUM,
                external_id="0xdup",
                timestamp=datetime(2024, 2, 3, 10, 0, tzinfo=timezone.utc),
            )
        ],
    )

    initial_response = client.post("/corrections", json=payload)
    response = client.post("/corrections", json=payload)

    assert initial_response.status_code == 201
    assert response.status_code == 409
    assert response.json() == {
        "detail": "Raw event cannot be consumed by more than one correction source: ARBITRUM/0xdup"
    }


def test_delete_is_by_id_and_allows_manual_recreate(
    client: TestClient,
    persist_raw_events: Callable[[list[LedgerEvent]], None],
) -> None:
    payload = _discard_payload(external_id="0xrestore")
    persist_raw_events(
        [
            raw_event(
                location=EventLocation.ARBITRUM,
                external_id="0xrestore",
                timestamp=datetime(2024, 2, 3, 10, 0, tzinfo=timezone.utc),
            )
        ],
    )

    created = client.post("/corrections", json=payload).json()
    delete_response = client.delete(f"/corrections/{created['id']}")
    recreated = client.post("/corrections", json=payload)

    assert delete_response.status_code == 204
    assert recreated.status_code == 201
    assert recreated.json()["sources"] == payload["sources"]


def test_get_lists_persisted_corrections_in_desc_order(
    client: TestClient,
    persist_correction: Callable[[LedgerCorrectionDraft], LedgerCorrection],
) -> None:
    older = LedgerCorrectionDraft(
        timestamp=datetime(2024, 2, 1, 12, 0, tzinfo=timezone.utc),
        legs=frozenset([LedgerLeg(asset_id=BTC, quantity=Decimal("1"), account_chain_id=LEDGER_WALLET)]),
    )
    newer = LedgerCorrectionDraft(
        timestamp=datetime(2024, 2, 2, 12, 0, tzinfo=timezone.utc),
        sources=frozenset([EventOrigin(location=EventLocation.BASE, external_id="0xorphan")]),
    )
    persisted_older = persist_correction(older)
    persisted_newer = persist_correction(newer)

    response = client.get("/corrections")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [str(persisted_newer.id), str(persisted_older.id)]


def test_delete_is_idempotent_for_missing_correction(client: TestClient) -> None:
    response = client.delete(f"/corrections/{uuid4()}")

    assert response.status_code == 204
    assert client.get("/corrections").json() == []
