from contextlib import asynccontextmanager
from time import perf_counter
from typing import Annotated, AsyncGenerator, Awaitable, Callable

from fastapi import Depends, FastAPI, Request, Response
from pydantic import Field
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from accounts import AccountRegistry
from api.dependencies import (
    get_corrected_events_repository,
    get_raw_events_repository,
    get_seed_events_repository,
    get_spam_correction_repository,
)
from config import ACCOUNTS_PATH, CORRECTIONS_DB_PATH, DB_PATH
from db.corrections import SpamCorrectionRepository
from db.repositories import CorrectedLedgerEventRepository, LedgerEventRepository, SeedEventRepository
from domain.correction import SeedEvent, Spam, SpamCorrectionSource
from domain.ledger import EventLocation, EventOrigin, LedgerEvent
from pydantic_base import StrictBaseModel


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI) -> AsyncGenerator[None, None]:
    engine = create_engine(f"sqlite:///{DB_PATH}", echo=True)
    corrections_engine = create_engine(f"sqlite:///{CORRECTIONS_DB_PATH}", echo=True)
    fastapi_app.state.sessionmaker = sessionmaker(engine)
    fastapi_app.state.corrections_sessionmaker = sessionmaker(corrections_engine)
    yield
    corrections_engine.dispose()
    engine.dispose()


app = FastAPI(lifespan=lifespan)


class ApiAccount(StrictBaseModel):
    account_chain_id: str
    name: str
    chain: str
    address: str
    skip_sync: bool


class ApiEventOrigin(StrictBaseModel):
    location: EventLocation
    external_id: str = Field(min_length=1)


class ApiSpamCorrection(StrictBaseModel):
    id: str
    event_origin: ApiEventOrigin
    source: SpamCorrectionSource


class ApiCreateSpamCorrectionRequest(StrictBaseModel):
    event_origin: ApiEventOrigin


class ApiDeleteSpamCorrectionRequest(StrictBaseModel):
    event_origin: ApiEventOrigin


def _api_spam_correction(record: Spam) -> ApiSpamCorrection:
    return ApiSpamCorrection(
        id=str(record.id),
        event_origin=ApiEventOrigin(
            location=record.event_origin.location,
            external_id=record.event_origin.external_id,
        ),
        source=record.source,
    )


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
def get_accounts() -> list[ApiAccount]:
    registry = AccountRegistry.from_path(ACCOUNTS_PATH)
    records = sorted(registry.records(), key=lambda record: record.account_chain_id)
    return [
        ApiAccount(
            account_chain_id=record.account_chain_id,
            name=record.name,
            chain=record.chain,
            address=record.address,
            skip_sync=record.skip_sync,
        )
        for record in records
    ]


@app.get("/spam-corrections")
def get_spam_corrections(
    repo: Annotated[SpamCorrectionRepository, Depends(get_spam_correction_repository)],
) -> list[ApiSpamCorrection]:
    return [_api_spam_correction(record) for record in repo.list() if record.source == SpamCorrectionSource.MANUAL]


@app.post("/spam-corrections", status_code=204)
def create_spam_correction(
    payload: ApiCreateSpamCorrectionRequest,
    repo: Annotated[SpamCorrectionRepository, Depends(get_spam_correction_repository)],
) -> Response:
    repo.mark_as_spam(
        EventOrigin(location=payload.event_origin.location, external_id=payload.event_origin.external_id),
        SpamCorrectionSource.MANUAL,
    )
    return Response(status_code=204)


@app.delete("/spam-corrections", status_code=204)
def delete_spam_correction(
    payload: ApiDeleteSpamCorrectionRequest,
    repo: Annotated[SpamCorrectionRepository, Depends(get_spam_correction_repository)],
) -> Response:
    repo.remove_spam_mark(
        EventOrigin(location=payload.event_origin.location, external_id=payload.event_origin.external_id)
    )
    return Response(status_code=204)
