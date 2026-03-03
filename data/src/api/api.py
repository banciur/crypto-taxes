from contextlib import asynccontextmanager
from datetime import datetime
from time import perf_counter
from typing import Annotated, AsyncGenerator, Awaitable, Callable, Iterable

from fastapi import Depends, FastAPI, Request, Response
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from accounts import AccountChainRecord, AccountRegistry
from api.dependencies import (
    get_corrected_events_repository,
    get_raw_events_repository,
    get_seed_events_repository,
    get_spam_correction_repository,
)
from config import CORRECTIONS_DB_PATH, DB_PATH
from db.corrections import SpamCorrectionRepository
from db.repositories import CorrectedLedgerEventRepository, LedgerEventRepository, SeedEventRepository
from domain.correction import SeedEvent, Spam
from domain.ledger import EventLocation, EventOrigin, LedgerEvent


class ApiSpamCorrection(Spam):
    timestamp: datetime


def _event_origin_key(event_origin: EventOrigin) -> tuple[EventLocation, str]:
    return event_origin.location, event_origin.external_id


def _api_spam_corrections(
    records: list[Spam],
    raw_event_timestamps: Iterable[tuple[EventOrigin, datetime]],
) -> list[ApiSpamCorrection]:
    records_by_origin = {_event_origin_key(record.event_origin): record for record in records}
    matched_timestamps_by_origin: dict[tuple[EventLocation, str], list[datetime]] = {
        key: [] for key in records_by_origin
    }
    ordered_origins: list[tuple[EventLocation, str]] = []

    for event_origin, timestamp in raw_event_timestamps:
        origin_key = _event_origin_key(event_origin)
        matched_timestamps = matched_timestamps_by_origin[origin_key]
        if len(matched_timestamps) == 0:
            ordered_origins.append(origin_key)
        matched_timestamps.append(timestamp)

    for origin_key, record in records_by_origin.items():
        matched_timestamps = matched_timestamps_by_origin[origin_key]
        if len(matched_timestamps) != 1:
            raise RuntimeError(
                "Spam correction must match exactly one raw event: "
                f"{record.event_origin.location.value}/{record.event_origin.external_id}"
            )

    return [
        ApiSpamCorrection(
            id=records_by_origin[origin_key].id,
            event_origin=records_by_origin[origin_key].event_origin,
            timestamp=matched_timestamps_by_origin[origin_key][0],
        )
        for origin_key in ordered_origins
    ]


def create_app(
    *,
    sessionmaker_factory: sessionmaker[Session] | None = None,
    corrections_sessionmaker_factory: sessionmaker[Session] | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(fastapi_app: FastAPI) -> AsyncGenerator[None, None]:
        engine: Engine | None = None
        corrections_engine: Engine | None = None

        if sessionmaker_factory is None:
            engine = create_engine(f"sqlite:///{DB_PATH}", echo=True)
            fastapi_app.state.sessionmaker = sessionmaker(engine)
        else:
            fastapi_app.state.sessionmaker = sessionmaker_factory

        if corrections_sessionmaker_factory is None:
            corrections_engine = create_engine(f"sqlite:///{CORRECTIONS_DB_PATH}", echo=True)
            fastapi_app.state.corrections_sessionmaker = sessionmaker(corrections_engine)
        else:
            fastapi_app.state.corrections_sessionmaker = corrections_sessionmaker_factory

        yield

        if corrections_engine is not None:
            corrections_engine.dispose()
        if engine is not None:
            engine.dispose()

    app = FastAPI(lifespan=lifespan)

    @app.middleware("http")
    async def print_process_time(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start_time = perf_counter()
        response = await call_next(request)
        process_time = perf_counter() - start_time
        print(f"Request time: {request.method} {request.url}: {process_time:.4f}s")
        return response

    @app.get("/raw-events")
    def get_raw_events(rr: Annotated[LedgerEventRepository, Depends(get_raw_events_repository)]) -> list[LedgerEvent]:
        return rr.list()

    @app.get("/corrected-events")
    def get_corrected_events(
        cr: Annotated[CorrectedLedgerEventRepository, Depends(get_corrected_events_repository)],
    ) -> list[LedgerEvent]:
        return cr.list()

    @app.get("/seed-events")
    def get_seed_events(sr: Annotated[SeedEventRepository, Depends(get_seed_events_repository)]) -> list[SeedEvent]:
        return sr.list()

    @app.get("/accounts")
    def get_accounts() -> list[AccountChainRecord]:
        return AccountRegistry.from_path().records()

    @app.get("/spam-corrections")
    def get_spam_corrections(
        repo: Annotated[SpamCorrectionRepository, Depends(get_spam_correction_repository)],
        raw_repo: Annotated[LedgerEventRepository, Depends(get_raw_events_repository)],
    ) -> list[ApiSpamCorrection]:
        records = repo.list()
        raw_event_timestamps = raw_repo.list_event_timestamps_for_origins(record.event_origin for record in records)
        return _api_spam_corrections(records, raw_event_timestamps)

    @app.post("/spam-corrections", status_code=204)
    def create_spam_correction(
        payload: EventOrigin,
        repo: Annotated[SpamCorrectionRepository, Depends(get_spam_correction_repository)],
    ) -> Response:
        repo.mark_as_spam(payload)
        return Response(status_code=204)

    @app.delete("/spam-corrections", status_code=204)
    def delete_spam_correction(
        payload: EventOrigin,
        repo: Annotated[SpamCorrectionRepository, Depends(get_spam_correction_repository)],
    ) -> Response:
        repo.remove_spam_mark(payload)
        return Response(status_code=204)

    return app


app = create_app()
