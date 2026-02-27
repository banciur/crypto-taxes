from __future__ import annotations

from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

import api.api as api_module
from db.corrections import init_corrections_db


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    main_db = tmp_path / "api-main.db"
    corrections_db = tmp_path / "api-corrections.db"
    corrections_session = init_corrections_db(db_file=corrections_db, reset=True)
    corrections_session.close()
    monkeypatch.setattr(api_module, "DB_PATH", main_db)
    monkeypatch.setattr(api_module, "CORRECTIONS_DB_PATH", corrections_db)
    with TestClient(api_module.app) as test_client:
        yield test_client


def _payload(*, location: str = "ARBITRUM", external_id: str = "0xabc") -> dict[str, object]:
    return {"event_origin": {"location": location, "external_id": external_id}}


def test_post_creates_and_get_lists_active_spam_corrections(client: TestClient) -> None:
    create_response = client.post("/spam-corrections", json=_payload())
    list_response = client.get("/spam-corrections")

    assert create_response.status_code == 204
    assert create_response.content == b""

    assert list_response.status_code == 200
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["event_origin"] == _payload()["event_origin"]
    assert listed[0]["source"] == "MANUAL"


def test_delete_hides_record_and_post_restores_same_id(client: TestClient) -> None:
    create_response = client.post("/spam-corrections", json=_payload(external_id="0xrestore"))
    created = client.get("/spam-corrections").json()[0]

    delete_response = client.request("DELETE", "/spam-corrections", json=_payload(external_id="0xrestore"))
    after_delete = client.get("/spam-corrections")
    restore_response = client.post("/spam-corrections", json=_payload(external_id="0xrestore"))
    restored = client.get("/spam-corrections").json()[0]

    assert create_response.status_code == 204
    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert after_delete.json() == []
    assert restore_response.status_code == 204
    assert restored["id"] == created["id"]


def test_duplicate_post_is_idempotent(client: TestClient) -> None:
    first_response = client.post("/spam-corrections", json=_payload(external_id="0xdup"))
    first_listed = client.get("/spam-corrections").json()
    second_response = client.post("/spam-corrections", json=_payload(external_id="0xdup"))

    listed = client.get("/spam-corrections").json()
    assert first_response.status_code == 204
    assert second_response.status_code == 204
    assert listed == first_listed


def test_delete_is_idempotent_for_missing_record(client: TestClient) -> None:
    response = client.request("DELETE", "/spam-corrections", json=_payload(external_id="0xmissing"))

    assert response.status_code == 204
    assert client.get("/spam-corrections").json() == []


def test_invalid_event_origin_payload_returns_422(client: TestClient) -> None:
    response = client.post("/spam-corrections", json=_payload(location="NOT_A_CHAIN"))

    assert response.status_code == 422
