from contextlib import asynccontextmanager
from time import perf_counter
from typing import AsyncGenerator, Awaitable, Callable

from fastapi import FastAPI, Request, Response
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from accounts import AccountChainRecord, AccountRegistry
from api.corrections import router as corrections_router
from api.events import router as events_router
from config import CORRECTIONS_DB_PATH, DB_PATH


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
            engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
            fastapi_app.state.sessionmaker = sessionmaker(engine)
        else:
            fastapi_app.state.sessionmaker = sessionmaker_factory

        if corrections_sessionmaker_factory is None:
            corrections_engine = create_engine(f"sqlite:///{CORRECTIONS_DB_PATH}", echo=False)
            fastapi_app.state.corrections_sessionmaker = sessionmaker(corrections_engine)
        else:
            fastapi_app.state.corrections_sessionmaker = corrections_sessionmaker_factory

        yield

        if corrections_engine is not None:
            corrections_engine.dispose()
        if engine is not None:
            engine.dispose()

    fastapi_app = FastAPI(lifespan=lifespan)

    @fastapi_app.middleware("http")
    async def print_process_time(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start_time = perf_counter()
        response = await call_next(request)
        process_time = perf_counter() - start_time
        print(f"Request time: {request.method} {request.url}: {process_time:.4f}s")
        return response

    fastapi_app.include_router(events_router)
    fastapi_app.include_router(corrections_router)

    @fastapi_app.get("/accounts")
    def get_accounts() -> list[AccountChainRecord]:
        return AccountRegistry.from_path().records()

    return fastapi_app


app = create_app()
