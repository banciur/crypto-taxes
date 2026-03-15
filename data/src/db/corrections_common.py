from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class CorrectionsBase(DeclarativeBase):
    pass


def init_corrections_db(*, db_path: Path, echo: bool = False, reset: bool = False) -> Session:
    from db import corrections_replacement, corrections_spam  # noqa: F401

    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=echo)
    if reset:
        CorrectionsBase.metadata.drop_all(engine)
    CorrectionsBase.metadata.create_all(engine)
    return sessionmaker(engine)()
