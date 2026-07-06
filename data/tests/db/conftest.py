from collections.abc import Generator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.ledger_corrections import CorrectionsBase
from db.price_overrides import PriceOverridesBase


@pytest.fixture(scope="function")
def corrections_session(db_engine: Engine) -> Generator[Session, None, None]:
    CorrectionsBase.metadata.create_all(db_engine)
    with sessionmaker(db_engine)() as session:
        yield session
    CorrectionsBase.metadata.drop_all(db_engine)


@pytest.fixture(scope="function")
def price_overrides_session(db_engine: Engine) -> Generator[Session, None, None]:
    PriceOverridesBase.metadata.create_all(db_engine)
    with sessionmaker(db_engine)() as session:
        yield session
    PriceOverridesBase.metadata.drop_all(db_engine)
