from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence, TypedDict

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint, create_engine, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from domain.ledger import EventLocation, WalletAddress
from type_defs import RawTxs


class TransactionsCacheBase(DeclarativeBase):
    pass


class MoralisTransactionOrm(TransactionsCacheBase):
    __tablename__ = "moralis_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location: Mapped[str] = mapped_column(String, nullable=False)
    hash: Mapped[str] = mapped_column(String, nullable=False)
    block_number: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_index: Mapped[int] = mapped_column(Integer, nullable=False)
    block_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("location", "hash", name="uq_moralis_location_hash"),
        Index("ix_moralis_hash", "hash"),
        Index("ix_moralis_order", "block_timestamp", "block_number", "transaction_index"),
    )


class MoralisSyncStateOrm(TransactionsCacheBase):
    __tablename__ = "moralis_sync_state"

    location: Mapped[str] = mapped_column(String, primary_key=True)
    address: Mapped[str] = mapped_column(String, primary_key=True)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TransactionRow(TypedDict):
    location: str
    hash: str
    block_number: int
    transaction_index: int
    block_timestamp: datetime
    payload: str


class TransactionsCacheRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert_transactions(self, records: Sequence[TransactionRow]) -> None:
        if not records:
            return

        stmt = insert(MoralisTransactionOrm).values(records)
        stmt = stmt.on_conflict_do_nothing(index_elements=["location", "hash"])
        self.session.execute(stmt)
        self.session.commit()

    def load_all_transactions(self) -> RawTxs:
        stmt = select(MoralisTransactionOrm).order_by(
            MoralisTransactionOrm.block_timestamp,
            MoralisTransactionOrm.block_number,
            MoralisTransactionOrm.transaction_index,
        )
        rows = self.session.execute(stmt).scalars().all()
        return [{**json.loads(row.payload), "location": EventLocation(row.location)} for row in rows]

    def last_synced_at(self, location: EventLocation, address: WalletAddress) -> datetime | None:
        stmt = (
            select(MoralisSyncStateOrm.last_synced_at)
            .where(MoralisSyncStateOrm.location == location.value, MoralisSyncStateOrm.address == str(address))
            .limit(1)
        )
        last_synced_at = self.session.scalar(stmt)
        if last_synced_at is None or last_synced_at.tzinfo is not None:
            return last_synced_at
        return last_synced_at.replace(tzinfo=timezone.utc)  # SQLite does not preserve timezone info for datetimes.

    def mark_synced(self, location: EventLocation, address: WalletAddress, when: datetime) -> None:
        stmt = insert(MoralisSyncStateOrm).values(
            {"location": location.value, "address": str(address), "last_synced_at": when}
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["location", "address"], set_={"last_synced_at": stmt.excluded.last_synced_at}
        )
        self.session.execute(stmt)
        self.session.commit()


def init_transactions_cache_db(*, db_path: Path, echo: bool = False, reset: bool = False) -> Session:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=echo)
    if reset:
        TransactionsCacheBase.metadata.drop_all(engine)
    TransactionsCacheBase.metadata.create_all(engine)
    return sessionmaker(engine)()
