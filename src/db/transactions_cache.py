from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint, create_engine, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

CACHE_DB_PATH = Path("data/transactions_cache.db")


class TransactionsCacheBase(DeclarativeBase):
    pass


class MoralisTransactionOrm(TransactionsCacheBase):
    __tablename__ = "moralis_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chain: Mapped[str] = mapped_column(String, nullable=False)
    hash: Mapped[str] = mapped_column(String, nullable=False)
    block_number: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_index: Mapped[int] = mapped_column(Integer, nullable=False)
    block_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("chain", "hash", name="uq_moralis_chain_hash"),
        Index("ix_moralis_hash", "hash"),
        Index("ix_moralis_order", "block_timestamp", "block_number", "transaction_index"),
    )


class TransactionsCacheRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert_transactions(self, records: list[dict[str, object]]) -> None:
        if not records:
            return

        stmt = sqlite_insert(MoralisTransactionOrm).values(records)
        stmt = stmt.on_conflict_do_nothing(index_elements=["chain", "hash"])
        self.session.execute(stmt)
        self.session.commit()

    def latest_block_timestamp(self, chain: str) -> datetime | None:
        stmt = (
            select(MoralisTransactionOrm.block_timestamp)
            .where(MoralisTransactionOrm.chain == chain)
            .order_by(MoralisTransactionOrm.block_timestamp.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)

    def load_all_transactions(self) -> list[dict[str, object]]:
        stmt = select(MoralisTransactionOrm).order_by(
            MoralisTransactionOrm.block_timestamp,
            MoralisTransactionOrm.block_number,
            MoralisTransactionOrm.transaction_index,
        )
        rows = self.session.execute(stmt).scalars().all()
        return [json.loads(row.payload) for row in rows]


def init_transactions_cache_db(
    echo: bool = False, *, db_file: str | Path = CACHE_DB_PATH, reset: bool = False
) -> Session:
    path = Path(db_file)
    if reset and path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(f"sqlite:///{path}", echo=echo)
    TransactionsCacheBase.metadata.create_all(engine)
    return sessionmaker(engine)()
