from collections.abc import Generator

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import Base
from domain.inventory import InventoryEngine
from tests.helpers.random_price_service import TestPriceService
from tests.helpers.time_utils import DEFAULT_TIME_GEN


@pytest.fixture(scope="module")
def db_engine() -> Generator[Engine, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def test_session(db_engine: Engine) -> Generator[Session, None, None]:
    Base.metadata.create_all(db_engine)
    with sessionmaker(db_engine)() as session:
        yield session
    Base.metadata.drop_all(db_engine)


@pytest.fixture(autouse=True)
def _reset_default_time_gen() -> None:
    DEFAULT_TIME_GEN.reset()


@pytest.fixture(scope="function")
def price_service() -> TestPriceService:
    return TestPriceService(seed=3)


@pytest.fixture(scope="function")
def inventory_engine(price_service: TestPriceService) -> InventoryEngine:
    return InventoryEngine(price_provider=price_service)
