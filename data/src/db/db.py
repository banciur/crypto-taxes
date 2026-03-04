from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base


def init_db(*, db_path: Path, echo: bool = False, reset: bool = False) -> Session:
    engine: Engine = create_engine(f"sqlite:///{db_path}", echo=echo)
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(engine)()
