from typing import Annotated, Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from db.corrections_store import SpamCorrectionRepository
from db.repositories import CorrectedLedgerEventRepository, LedgerEventRepository, SeedEventRepository
from services.spam_correction_service import SpamCorrectionService


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


def get_spam_correction_service(
    repo: Annotated[SpamCorrectionRepository, Depends(get_spam_correction_repository)],
) -> SpamCorrectionService:
    return SpamCorrectionService(repo)
