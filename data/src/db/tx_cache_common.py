from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import DeclarativeBase, Session

from db.session import init_db_session


class TransactionsCacheBase(DeclarativeBase):
    pass


def init_transactions_cache_db(*, db_path: Path, echo: bool = False, reset: bool = False) -> Session:
    def _ensure_models_loaded() -> None:
        from db import tx_cache_coinbase, tx_cache_moralis  # noqa: F401 unused-import

    return init_db_session(
        db_path=db_path,
        metadata=TransactionsCacheBase.metadata,
        ensure_models_loaded=_ensure_models_loaded,
        echo=echo,
        reset=reset,
    )
