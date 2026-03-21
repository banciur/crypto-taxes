from __future__ import annotations

from collections.abc import Callable, Generator
from datetime import datetime
from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.api as api
from accounts import KRAKEN_ACCOUNT_ID
from db.ledger_corrections import CorrectionsBase, LedgerCorrectionRepository
from db.models import Base
from db.repositories import LedgerEventRepository
from domain.correction import LedgerCorrection
from domain.ledger import EventLocation, EventOrigin, LedgerEvent, LedgerEventId, LedgerLeg
from tests.constants import BTC, EUR


@pytest.fixture()
def db_engine_factory() -> Generator[Callable[[], Engine], None, None]:
    engines: list[Engine] = []

    def make_engine() -> Engine:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        engines.append(engine)
        return engine

    yield make_engine

    for engine in engines:
        engine.dispose()


@pytest.fixture()
def client(db_engine_factory: Callable[[], Engine]) -> Generator[TestClient, None, None]:
    main_engine = db_engine_factory()
    corrections_engine = db_engine_factory()
    Base.metadata.create_all(main_engine)
    CorrectionsBase.metadata.create_all(corrections_engine)
    app = api.create_app(
        sessionmaker_factory=sessionmaker(main_engine),
        corrections_sessionmaker_factory=sessionmaker(corrections_engine),
    )
    with TestClient(app) as test_client:
        yield test_client


def raw_event(
    *,
    location: EventLocation,
    external_id: str,
    timestamp: datetime,
) -> LedgerEvent:
    return LedgerEvent(
        id=LedgerEventId(uuid4()),
        timestamp=timestamp,
        event_origin=EventOrigin(location=location, external_id=external_id),
        ingestion="api_test",
        legs=[
            LedgerLeg(asset_id=BTC, quantity=Decimal("0.1"), account_chain_id=KRAKEN_ACCOUNT_ID, is_fee=False),
            LedgerLeg(asset_id=EUR, quantity=Decimal("-100"), account_chain_id=KRAKEN_ACCOUNT_ID, is_fee=False),
        ],
    )


@pytest.fixture()
def persist_raw_events(client: TestClient) -> Callable[[list[LedgerEvent]], None]:
    def persist(events: list[LedgerEvent]) -> None:
        app = cast(FastAPI, client.app)
        with app.state.sessionmaker() as session:
            LedgerEventRepository(session).create_many(events)

    return persist


@pytest.fixture()
def persist_correction(client: TestClient) -> Callable[[LedgerCorrection], None]:
    def persist(correction: LedgerCorrection) -> None:
        app = cast(FastAPI, client.app)
        with app.state.corrections_sessionmaker() as session:
            LedgerCorrectionRepository(session).create(correction)

    return persist
