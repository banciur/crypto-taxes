from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from db.system_state import SystemStateRepository
from domain.system_state import (
    SystemState,
    SystemStateError,
    SystemStateStage,
    SystemStateStatus,
)


@pytest.fixture()
def persist_system_state(client: TestClient) -> Callable[[SystemState], SystemState]:
    def persist(state: SystemState) -> SystemState:
        app = cast(FastAPI, client.app)
        with app.state.sessionmaker() as session:
            return SystemStateRepository(session).replace(state)

    return persist


def test_get_system_state_returns_not_run_when_state_is_missing(client: TestClient) -> None:
    response = client.get("/system-state")
    expected = SystemState.not_run()

    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")


def test_get_system_state_returns_persisted_latest_state(
    client: TestClient,
    persist_system_state: Callable[[SystemState], SystemState],
) -> None:
    state = SystemState(
        status=SystemStateStatus.FAILED,
        stage=SystemStateStage.CORRECTIONS,
        started_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        finished_at=datetime(2026, 1, 2, 3, 5, 6, tzinfo=UTC),
        error=SystemStateError(
            exception_type="RuntimeError",
            message="boom",
            traceback="Traceback text",
        ),
    )
    persisted = persist_system_state(state)

    response = client.get("/system-state")

    assert response.status_code == 200
    assert response.json() == persisted.model_dump(mode="json")
