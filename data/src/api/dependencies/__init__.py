from typing import Annotated, Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from db.corrections_replacement import ReplacementCorrectionRepository
from db.corrections_spam import SpamCorrectionRepository
from db.repositories import CorrectedLedgerEventRepository, LedgerEventRepository, SeedEventRepository


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


def get_seed_events_repository(session: Annotated[Session, Depends(get_session)]) -> SeedEventRepository:
    return SeedEventRepository(session)


def get_spam_correction_repository(
    session: Annotated[Session, Depends(get_corrections_session)],
) -> SpamCorrectionRepository:
    return SpamCorrectionRepository(session)


def get_replacement_correction_repository(
    session: Annotated[Session, Depends(get_corrections_session)],
) -> ReplacementCorrectionRepository:
    return ReplacementCorrectionRepository(session)
