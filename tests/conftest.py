from typing import Generator

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base
from tests.helpers.test_price_service import TestPriceService

engine: Engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
session_factory = sessionmaker(engine)


@pytest.fixture(scope="function")
def test_session() -> Generator[Session, None, None]:
    with session_factory() as session:
        yield session


@pytest.fixture(scope="function", autouse=True)
def reset_db() -> Generator[None, None, None]:
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def price_service() -> TestPriceService:
    return TestPriceService(seed=3)
