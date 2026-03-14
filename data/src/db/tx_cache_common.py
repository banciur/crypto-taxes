from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class TransactionsCacheBase(DeclarativeBase):
    pass


def add_utc_to_datetime(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def init_transactions_cache_db(*, db_path: Path, echo: bool = False, reset: bool = False) -> Session:
    from db import tx_cache_coinbase, tx_cache_moralis  # noqa: F401 unused-import

    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=echo)
    if reset:
        TransactionsCacheBase.metadata.drop_all(engine)
    TransactionsCacheBase.metadata.create_all(engine)
    return sessionmaker(engine)()
