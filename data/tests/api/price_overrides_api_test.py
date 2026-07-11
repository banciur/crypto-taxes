from typing import TypedDict
from uuid import uuid4

from fastapi.testclient import TestClient

from tests.constants import BTC


class OriginPayload(TypedDict):
    location: str
    external_id: str


class OverridePayload(TypedDict, total=False):
    event_origin: OriginPayload
    asset_id: str
    rate_eur: str
    note: str | None


def _override_payload(*, external_id: str = "0xabc", asset_id: str = BTC, rate_eur: str = "40000") -> OverridePayload:
    return {
        "event_origin": OriginPayload(location="ETHEREUM", external_id=external_id),
        "asset_id": asset_id,
        "rate_eur": rate_eur,
        "note": "manual price",
    }


def test_post_creates_and_get_lists_the_override(client: TestClient) -> None:
    payload = _override_payload()

    create_response = client.post("/price-overrides", json=payload)
    list_response = client.get("/price-overrides")

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["event_origin"] == payload["event_origin"]
    assert created["asset_id"] == payload["asset_id"]
    assert created["rate_eur"] == payload["rate_eur"]
    assert created["note"] == payload["note"]
    assert "id" in created

    assert list_response.status_code == 200
    assert list_response.json() == [created]


def test_post_rejects_a_second_override_for_the_same_event_and_asset(client: TestClient) -> None:
    first = client.post("/price-overrides", json=_override_payload(rate_eur="40000"))

    response = client.post("/price-overrides", json=_override_payload(rate_eur="41000"))

    assert first.status_code == 201
    assert response.status_code == 409
    # The rejected create is rolled back, leaving the original override intact.
    assert client.get("/price-overrides").json() == [first.json()]


def test_post_rejects_non_positive_rate(client: TestClient) -> None:
    response = client.post("/price-overrides", json=_override_payload(rate_eur="0"))

    assert response.status_code == 422


def test_post_rejects_missing_event_origin(client: TestClient) -> None:
    payload = _override_payload()
    del payload["event_origin"]

    response = client.post("/price-overrides", json=payload)

    assert response.status_code == 422


def test_delete_removes_override(client: TestClient) -> None:
    created = client.post("/price-overrides", json=_override_payload()).json()

    delete_response = client.delete(f"/price-overrides/{created['id']}")

    assert delete_response.status_code == 204
    assert client.get("/price-overrides").json() == []


def test_delete_is_idempotent_for_missing_override(client: TestClient) -> None:
    response = client.delete(f"/price-overrides/{uuid4()}")

    assert response.status_code == 204
    assert client.get("/price-overrides").json() == []
