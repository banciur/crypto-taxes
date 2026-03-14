# This file is completely vibed.
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal, cast

from pydantic import ConfigDict, Field, field_validator, model_validator

from clients.coinbase import CoinbaseClient
from db.tx_cache_coinbase import CoinbaseCacheRepository
from pydantic_base import StrictBaseModel
from services.moralis import SyncMode
from utils.misc import utc_now

logger = logging.getLogger(__name__)


class CoinbaseMoney(StrictBaseModel):
    amount: Decimal
    currency: str


class CoinbaseAccount(StrictBaseModel):
    id: str
    name: str
    primary: bool
    type: str
    balance: CoinbaseMoney
    created_at: datetime
    updated_at: datetime
    resource: str
    resource_path: str
    currency: dict[str, Any]
    allow_deposits: bool
    allow_withdrawals: bool
    portfolio_id: str

    @field_validator("created_at", "updated_at")
    @classmethod
    def _ensure_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Coinbase account timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)


class CoinbaseNetwork(StrictBaseModel):
    hash: str | None = None
    network_name: str | None = None
    status: str
    transaction_fee: CoinbaseMoney | None = None


class CoinbaseCounterparty(StrictBaseModel):
    address: str | None = None
    id: str | None = None
    name: str | None = None
    resource: str


class CoinbaseBuy(StrictBaseModel):
    fee: CoinbaseMoney | None = None
    id: str
    payment_method_name: str | None = None
    subtotal: CoinbaseMoney | None = None
    total: CoinbaseMoney | None = None


class CoinbaseSell(StrictBaseModel):
    fee: CoinbaseMoney | None = None
    id: str
    payment_method_name: str | None = None
    subtotal: CoinbaseMoney | None = None
    total: CoinbaseMoney | None = None


class CoinbaseTrade(StrictBaseModel):
    fee: CoinbaseMoney | None = None
    id: str
    payment_method_name: str | None = None


class CoinbaseTransaction(StrictBaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    amount: CoinbaseMoney
    created_at: datetime
    id: str
    native_amount: CoinbaseMoney
    resource: str
    resource_path: str
    status: str
    type: str
    buy: CoinbaseBuy | None = None
    sell: CoinbaseSell | None = None
    trade: CoinbaseTrade | None = None
    network: CoinbaseNetwork | None = None
    idem: str | None = None
    to: CoinbaseCounterparty | None = None
    from_: CoinbaseCounterparty | None = Field(default=None, alias="from")
    description: str | None = None

    @field_validator("created_at")
    @classmethod
    def _ensure_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Coinbase transaction timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @property
    def account_id(self) -> str:
        parts = self.resource_path.split("/")
        if len(parts) < 6 or parts[1:3] != ["v2", "accounts"]:
            raise ValueError(f"Unexpected Coinbase transaction resource path: {self.resource_path}")
        return parts[3]


class CoinbaseAccountHistory(StrictBaseModel):
    fetched_at: datetime
    order: Literal["asc", "desc"]
    account_count: int
    transaction_count: int
    accounts: list[CoinbaseAccount]
    transactions: list[CoinbaseTransaction]

    @field_validator("fetched_at")
    @classmethod
    def _ensure_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Coinbase account-history fetched_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def _validate_counts(self) -> CoinbaseAccountHistory:
        if self.account_count != len(self.accounts):
            raise ValueError(f"account_count={self.account_count} does not match payload size {len(self.accounts)}")
        if self.transaction_count != len(self.transactions):
            raise ValueError(
                f"transaction_count={self.transaction_count} does not match payload size {len(self.transactions)}"
            )
        return self

    @property
    def accounts_by_id(self) -> dict[str, CoinbaseAccount]:
        return {account.id: account for account in self.accounts}


class CoinbaseService:
    _ORDER = "desc"

    def __init__(
        self,
        client: CoinbaseClient,
        cache_repo: CoinbaseCacheRepository,
        now_fn: Callable[[], datetime] = utc_now,
    ) -> None:
        self.client = client
        self.cache = cache_repo
        self._now = now_fn

    def get_history(self, sync_mode: SyncMode = SyncMode.BUDGET) -> CoinbaseAccountHistory:
        self._ensure_history_synced(sync_mode)
        return CoinbaseAccountHistory.model_validate(self.cache.load_history_payload())

    def _ensure_history_synced(self, sync_mode: SyncMode) -> None:
        last_synced_at = self.cache.last_synced_at()
        should_fetch = sync_mode == SyncMode.FRESH
        if sync_mode == SyncMode.BUDGET and (last_synced_at is None or last_synced_at.date() < self._now().date()):
            should_fetch = True

        if not should_fetch:
            logger.info("Coinbase history already synced today; skipping fetch")
            return

        self._refresh_history()

    def _refresh_history(self) -> None:
        accounts = self.client.fetch_accounts()
        transactions = self.client.fetch_transactions(order=self._ORDER, accounts=accounts)
        history = CoinbaseAccountHistory.model_validate(
            {
                "fetched_at": self._now(),
                "order": self._ORDER,
                "account_count": len(accounts),
                "transaction_count": len(transactions),
                "accounts": accounts,
                "transactions": transactions,
            }
        )
        self._replace_history(history)

    def _replace_history(self, history: CoinbaseAccountHistory) -> None:
        payload = history.model_dump(mode="json")
        self.cache.replace_history(
            fetched_at=history.fetched_at,
            order=history.order,
            accounts=cast(list[dict[str, Any]], payload["accounts"]),
            transactions=cast(list[dict[str, Any]], payload["transactions"]),
        )
