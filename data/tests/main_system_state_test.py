from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from accounts import KRAKEN_ACCOUNT_ID
from corrections.validation import CorrectionValidationError
from db.system_state import SystemStateRepository
from domain.ledger import EventLocation, EventOrigin
from domain.system_state import (
    SystemStateStage,
    SystemStateStatus,
)
from domain.wallet_projection import WalletBalanceIssue, WalletProjectionError
from main import (
    _run_system_state_stage,
    _system_state_error_from_exception,
)
from tests.constants import ETH

STARTED_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def test_run_system_state_stage_persists_running_state_and_returns_action_result(test_session: Session) -> None:
    repository = SystemStateRepository(test_session)

    result = _run_system_state_stage(
        repository,
        SystemStateStage.RAW_IMPORT,
        started_at=STARTED_AT,
        action=lambda: "stage-result",
    )

    state = repository.get()
    assert result == "stage-result"
    assert state.status == SystemStateStatus.RUNNING
    assert state.stage == SystemStateStage.RAW_IMPORT
    assert state.started_at == STARTED_AT
    assert state.finished_at is None
    assert state.error is None


def test_run_system_state_stage_persists_failed_state_and_reraises(test_session: Session) -> None:
    repository = SystemStateRepository(test_session)

    def fail() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        _run_system_state_stage(
            repository,
            SystemStateStage.CORRECTIONS,
            started_at=STARTED_AT,
            action=fail,
        )

    state = repository.get()
    assert state.status == SystemStateStatus.FAILED
    assert state.stage == SystemStateStage.CORRECTIONS
    assert state.started_at == STARTED_AT
    assert state.finished_at is not None
    assert state.error is not None
    assert state.error.exception_type == "RuntimeError"
    assert state.error.message == "boom"
    assert state.error.traceback is not None
    assert "RuntimeError: boom" in state.error.traceback


def test_correction_validation_error_maps_to_system_state_error() -> None:
    message = "Correction source must match exactly one raw event: BASE/evt-1"

    state_error = _system_state_error_from_exception(CorrectionValidationError(message))

    assert state_error.exception_type == "CorrectionValidationError"
    assert state_error.message == message
    assert state_error.traceback is not None


def test_unexpected_exception_maps_to_traceback_system_state_error() -> None:
    try:
        raise RuntimeError("boom")
    except RuntimeError as error:
        state_error = _system_state_error_from_exception(error)

    assert state_error.exception_type == "RuntimeError"
    assert state_error.message == "boom"
    assert state_error.traceback is not None
    assert "RuntimeError: boom" in state_error.traceback


def test_wallet_projection_error_maps_to_system_state_error() -> None:
    event = EventOrigin(location=EventLocation.BASE, external_id="evt-2")
    issue = WalletBalanceIssue(
        account_chain_id=KRAKEN_ACCOUNT_ID,
        asset_id=ETH,
        attempted_delta=Decimal("-1.5"),
        available_balance=Decimal("1.0"),
        missing_balance=Decimal("0.5"),
    )

    try:
        raise WalletProjectionError(event=event, issues=[issue])
    except WalletProjectionError as error:
        state_error = _system_state_error_from_exception(error)

    assert state_error.exception_type == "WalletProjectionError"
    assert "would go negative" in state_error.message
    assert state_error.traceback is not None
    assert "WalletProjectionError" in state_error.traceback
