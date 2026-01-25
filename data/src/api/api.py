from contextlib import asynccontextmanager
from time import perf_counter
from typing import Annotated, AsyncGenerator, Awaitable, Callable

from fastapi import Depends, FastAPI, Request, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.dependencies import get_corrected_events_repository, get_raw_events_repository, get_seed_events_repository
from config import DB_FILE
from db.repositories import CorrectedLedgerEventRepository, LedgerEventRepository, SeedEventRepository
from domain.correction import SeedEvent
from domain.ledger import LedgerEvent


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI) -> AsyncGenerator[None, None]:
    engine = create_engine(f"sqlite:///{DB_FILE}", echo=True)
    fastapi_app.state.sessionmaker = sessionmaker(engine)
    yield
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
