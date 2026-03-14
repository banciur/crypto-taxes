# This file is completely vibed.
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Sequence, TypedDict

from sqlalchemy import DateTime, Index, Integer, String, Text, delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from db.tx_cache_common import TransactionsCacheBase
from utils.misc import add_utc_to_datetime


class CoinbaseAccountOrm(TransactionsCacheBase):
    __tablename__ = "coinbase_accounts"

    account_id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (Index("ix_coinbase_accounts_updated_at", "updated_at"),)


class CoinbaseTransactionOrm(TransactionsCacheBase):
    __tablename__ = "coinbase_transactions"

    transaction_id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_coinbase_transactions_created_at", "created_at"),
        Index("ix_coinbase_transactions_account_id", "account_id"),
        Index("ix_coinbase_transactions_type", "type"),
    )


class CoinbaseCacheStateOrm(TransactionsCacheBase):
    __tablename__ = "coinbase_cache_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    order: Mapped[str] = mapped_column(String, nullable=False)
    account_count: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_count: Mapped[int] = mapped_column(Integer, nullable=False)


class CoinbaseAccountRow(TypedDict):
    account_id: str
    created_at: datetime
    updated_at: datetime
    payload: str


class CoinbaseTransactionRow(TypedDict):
    transaction_id: str
    account_id: str
    created_at: datetime
    type: str
    payload: str


class CoinbaseCacheRepository:
    _STATE_ROW_ID = 1

    def __init__(self, session: Session):
        self.session = session

    def has_history(self) -> bool:
        return self.session.get(CoinbaseCacheStateOrm, self._STATE_ROW_ID) is not None

    def last_synced_at(self) -> datetime | None:
        state = self.session.get(CoinbaseCacheStateOrm, self._STATE_ROW_ID)
        if state is None:
            return None
        return add_utc_to_datetime(state.fetched_at)

    def replace_history(
        self,
        *,
        fetched_at: datetime,
        order: str,
        accounts: Sequence[dict[str, Any]],
        transactions: Sequence[dict[str, Any]],
    ) -> None:
        account_rows: list[CoinbaseAccountRow] = [
            {
                "account_id": str(account["id"]),
                "created_at": datetime.fromisoformat(str(account["created_at"]).replace("Z", "+00:00")).astimezone(
                    timezone.utc
                ),
                "updated_at": datetime.fromisoformat(str(account["updated_at"]).replace("Z", "+00:00")).astimezone(
                    timezone.utc
                ),
                "payload": json.dumps(account),
            }
            for account in accounts
        ]
        transaction_rows: list[CoinbaseTransactionRow] = [
            {
                "transaction_id": str(transaction["id"]),
                "account_id": str(transaction["resource_path"]).split("/")[3],
                "created_at": datetime.fromisoformat(str(transaction["created_at"]).replace("Z", "+00:00")).astimezone(
                    timezone.utc
                ),
                "type": str(transaction["type"]),
                "payload": json.dumps(transaction),
            }
            for transaction in transactions
        ]

        self.session.execute(delete(CoinbaseTransactionOrm))
        self.session.execute(delete(CoinbaseAccountOrm))
        self.session.execute(delete(CoinbaseCacheStateOrm))
        if account_rows:
            self.session.execute(insert(CoinbaseAccountOrm).values(account_rows))
        if transaction_rows:
            self.session.execute(insert(CoinbaseTransactionOrm).values(transaction_rows))
        self.session.execute(
            insert(CoinbaseCacheStateOrm).values(
                {
                    "id": self._STATE_ROW_ID,
                    "fetched_at": fetched_at,
                    "order": order,
                    "account_count": len(accounts),
                    "transaction_count": len(transactions),
                }
            )
        )
        self.session.commit()

    def load_history_payload(self) -> dict[str, object]:
        state = self.session.get(CoinbaseCacheStateOrm, self._STATE_ROW_ID)
        if state is None:
            raise ValueError("Coinbase cache does not contain account history")
        fetched_at = add_utc_to_datetime(state.fetched_at)
        assert fetched_at is not None

        order_by_created_at = (
            CoinbaseTransactionOrm.created_at.desc()
            if state.order == "desc"
            else CoinbaseTransactionOrm.created_at.asc()
        )
        transaction_rows = self.session.execute(
            select(CoinbaseTransactionOrm).order_by(order_by_created_at, CoinbaseTransactionOrm.transaction_id)
        ).scalars()
        account_rows = self.session.execute(
            select(CoinbaseAccountOrm).order_by(CoinbaseAccountOrm.account_id)
        ).scalars()

        return {
            "fetched_at": fetched_at.isoformat().replace("+00:00", "Z"),
            "order": state.order,
            "account_count": state.account_count,
            "transaction_count": state.transaction_count,
            "accounts": [json.loads(row.payload) for row in account_rows],
            "transactions": [json.loads(row.payload) for row in transaction_rows],
        }
