from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base


def init_db(*, db_path: Path, echo: bool = False, reset: bool = False) -> Session:
    if reset and db_path.exists():
        db_path.unlink()

    engine: Engine = create_engine(f"sqlite:///{db_path}", echo=echo)

    Base.metadata.create_all(engine)
    return sessionmaker(engine)()
