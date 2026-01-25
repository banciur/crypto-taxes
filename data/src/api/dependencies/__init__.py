from typing import Annotated, Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from db.repositories import CorrectedLedgerEventRepository, LedgerEventRepository, SeedEventRepository


def get_session(request: Request) -> Generator[Session, None, None]:
    with request.app.state.sessionmaker() as session:
        yield session


def get_corrected_events_repository(
    session: Annotated[Session, Depends(get_session)],
) -> CorrectedLedgerEventRepository:
    return CorrectedLedgerEventRepository(session)


def get_raw_events_repository(session: Annotated[Session, Depends(get_session)]) -> LedgerEventRepository:
    return LedgerEventRepository(session)


def get_seed_events_repository(session: Annotated[Session, Depends(get_session)]) -> SeedEventRepository:
    return SeedEventRepository(session)
