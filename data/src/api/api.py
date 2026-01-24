from contextlib import asynccontextmanager
from typing import Annotated, AsyncGenerator

from fastapi import Depends, FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.dependencies import get_session
from config import DB_FILE
from db.repositories import CorrectedLedgerEventRepository
from domain.ledger import LedgerEvent


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI) -> AsyncGenerator[None, None]:
    engine = create_engine(f"sqlite:///{DB_FILE}", echo=True)
    fastapi_app.state.sessionmaker = sessionmaker(engine)
    yield
    engine.dispose()


app = FastAPI(lifespan=lifespan)


@app.get("/events")
def get_events(session: Annotated[Session, Depends(get_session)]) -> list[LedgerEvent]:
    r = CorrectedLedgerEventRepository(session)
    return r.list()
