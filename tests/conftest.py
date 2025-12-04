from typing import Generator

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base
from domain.inventory import InventoryEngine
from domain.wallet_balance_tracker import WalletBalanceTracker
from tests.helpers.random_price_service import TestPriceService
from tests.helpers.time_utils import DEFAULT_TIME_GEN

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


@pytest.fixture(autouse=True)
def _reset_default_time_gen() -> None:
    DEFAULT_TIME_GEN.reset()


@pytest.fixture(scope="function")
def price_service() -> TestPriceService:
    return TestPriceService(seed=3)


@pytest.fixture(scope="function")
def inventory_engine(price_service: TestPriceService) -> InventoryEngine:
    return InventoryEngine(price_provider=price_service, wallet_balance_tracker=WalletBalanceTracker())
