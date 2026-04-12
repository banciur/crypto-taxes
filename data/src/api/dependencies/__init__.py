from typing import Annotated, Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from db.ledger_corrections import LedgerCorrectionRepository
from db.repositories import CorrectedLedgerEventRepository, LedgerEventRepository
from db.wallet_projection import WalletProjectionRepository


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


def get_wallet_projection_repository(
    session: Annotated[Session, Depends(get_session)],
) -> WalletProjectionRepository:
    return WalletProjectionRepository(session)
