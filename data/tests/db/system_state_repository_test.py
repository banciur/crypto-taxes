from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from db.system_state import SystemStateRepository
from domain.system_state import (
    SystemState,
    SystemStateError,
    SystemStateStage,
    SystemStateStatus,
)

STARTED_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
FINISHED_AT = datetime(2026, 1, 2, 3, 5, 6, tzinfo=UTC)


@pytest.fixture()
def repo(test_session: Session) -> SystemStateRepository:
    return SystemStateRepository(test_session)


def _assert_replace_preserves_domain_state(repo: SystemStateRepository, state: SystemState) -> None:
    persisted = repo.replace(state)
    reloaded = repo.get()

    assert persisted == state
    assert reloaded == state


def test_get_returns_not_run_when_state_is_missing(repo: SystemStateRepository) -> None:
    assert repo.get() == SystemState.not_run()


@pytest.mark.parametrize(
    "state",
    [
        SystemState.not_run(),
        SystemState(
            status=SystemStateStatus.RUNNING,
            stage=SystemStateStage.RAW_IMPORT,
            started_at=STARTED_AT,
        ),
        SystemState(
            status=SystemStateStatus.COMPLETED,
            started_at=STARTED_AT,
            finished_at=FINISHED_AT,
        ),
        SystemState(
            status=SystemStateStatus.FAILED,
            stage=SystemStateStage.WALLET_PROJECTION,
            started_at=STARTED_AT,
            finished_at=FINISHED_AT,
            error=SystemStateError(
                exception_type="WalletProjectionFailed",
                message="Wallet projection failed",
            ),
        ),
        SystemState(
            status=SystemStateStatus.FAILED,
            stage=SystemStateStage.CORRECTIONS,
            started_at=STARTED_AT,
            finished_at=FINISHED_AT,
            error=SystemStateError(
                exception_type="RuntimeError",
                message="boom",
                traceback="Traceback text",
            ),
        ),
    ],
)
def test_replace_preserves_domain_state(repo: SystemStateRepository, state: SystemState) -> None:
    _assert_replace_preserves_domain_state(repo, state)
