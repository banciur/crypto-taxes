from collections.abc import Generator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.corrections_common import CorrectionsBase


@pytest.fixture(scope="function")
def corrections_session(db_engine: Engine) -> Generator[Session, None, None]:
    CorrectionsBase.metadata.create_all(db_engine)
    with sessionmaker(db_engine)() as session:
        yield session
    CorrectionsBase.metadata.drop_all(db_engine)
