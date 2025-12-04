from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base


def init_db(echo: bool = False, *, db_file: str | Path = "crypto_taxes.db", reset: bool = False) -> Session:
    path = Path(db_file)
    if reset and path.exists():
        path.unlink()

    engine: Engine = create_engine(f"sqlite:///{path}", echo=echo)

    Base.metadata.create_all(engine)
    return sessionmaker(engine)()
