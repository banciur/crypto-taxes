from typing import Annotated, Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from db.acquisition_disposal import AcquisitionDisposalProjectionRepository
from db.ledger_corrections import LedgerCorrectionRepository
from db.ledger_events import CorrectedLedgerEventRepository, LedgerEventRepository
from db.system_state import SystemStateRepository
from db.wallet_projection import WalletBalanceRepository


def get_session(request: Request) -> Generator[Session, None, None]:
    with request.app.state.sessionmaker() as session:
        yield session


def get_corrections_session(request: Request) -> Generator[Session, None, None]:
    with request.app.state.corrections_sessionmaker() as session:
        yield session


def get_corrected_events_repository(
    session: Annotated[Session, Depends(get_session)],
) -> CorrectedLedgerEventRepository:
    return CorrectedLedgerEventRepository(session)


def get_raw_events_repository(session: Annotated[Session, Depends(get_session)]) -> LedgerEventRepository:
    return LedgerEventRepository(session)


def get_correction_repository(
    session: Annotated[Session, Depends(get_corrections_session)],
) -> LedgerCorrectionRepository:
    return LedgerCorrectionRepository(session)


def get_wallet_balance_repository(
    session: Annotated[Session, Depends(get_session)],
) -> WalletBalanceRepository:
    return WalletBalanceRepository(session)


def get_system_state_repository(
    session: Annotated[Session, Depends(get_session)],
) -> SystemStateRepository:
    return SystemStateRepository(session)


def get_acquisition_disposal_projection_repository(
    session: Annotated[Session, Depends(get_session)],
) -> AcquisitionDisposalProjectionRepository:
    return AcquisitionDisposalProjectionRepository(session)
