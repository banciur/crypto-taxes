from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session, sessionmaker


def init_db_session(
    *,
    db_path: Path,
    metadata: MetaData,
    ensure_models_loaded: Callable[[], None] | None = None,
    echo: bool = False,
    reset: bool = False,
) -> Session:
    if ensure_models_loaded is not None:
        ensure_models_loaded()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=echo)
    if reset:
        metadata.drop_all(engine)
    metadata.create_all(engine)
    return sessionmaker(engine)()
