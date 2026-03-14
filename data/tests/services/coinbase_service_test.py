# This file is completely vibed.
from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any, NamedTuple, cast

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from clients.coinbase import CoinbaseClient
from db.tx_cache_coinbase import CoinbaseCacheRepository
from db.tx_cache_common import TransactionsCacheBase
from services.coinbase import CoinbaseService
from services.moralis import SyncMode

FIXED_NOW = datetime(2026, 3, 14, 12, tzinfo=timezone.utc)


def _account(account_id: str = "btc-wallet") -> dict[str, object]:
    return {
        "id": account_id,
        "name": "BTC Wallet",
        "primary": True,
        "type": "wallet",
        "balance": {"amount": "0.1", "currency": "BTC"},
        "created_at": "2026-03-11T23:33:26Z",
        "updated_at": "2026-03-11T23:33:26Z",
        "resource": "account",
        "resource_path": f"/v2/accounts/{account_id}",
        "currency": {"code": "BTC"},
        "allow_deposits": True,
        "allow_withdrawals": True,
        "portfolio_id": f"portfolio-{account_id}",
    }


def _transaction(
    transaction_id: str = "tx-1",
    account_id: str = "btc-wallet",
    *,
    created_at: str = "2025-02-20T17:17:42Z",
) -> dict[str, object]:
    return {
        "amount": {"amount": "0.1", "currency": "BTC"},
        "created_at": created_at,
        "id": transaction_id,
        "native_amount": {"amount": "1000.00", "currency": "EUR"},
        "resource": "transaction",
        "resource_path": f"/v2/accounts/{account_id}/transactions/{transaction_id}",
        "status": "completed",
        "type": "send",
        "network": {"hash": "hash-1", "network_name": "bitcoin", "status": "confirmed"},
    }


class _StubCoinbaseClient:
    def __init__(self) -> None:
        self.accounts: list[dict[str, object]] = []
        self.transactions: list[dict[str, object]] = []
        self.calls: list[tuple[str, str | None]] = []

    def fetch_accounts(self) -> list[dict[str, object]]:
        self.calls.append(("fetch_accounts", None))
        return self.accounts

    def fetch_transactions(
        self,
        *,
        order: str = "desc",
        accounts: list[dict[str, object]] | None = None,
    ) -> list[dict[str, object]]:
        self.calls.append(("fetch_transactions", order))
        assert accounts == self.accounts
        return self.transactions


class _StubClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class _ServiceTestContext(NamedTuple):
    service: CoinbaseService
    client: _StubCoinbaseClient
    cache_repo: CoinbaseCacheRepository
    clock: _StubClock


@pytest.fixture()
def test_ctx(db_engine: Engine) -> Generator[_ServiceTestContext, None, None]:
    TransactionsCacheBase.metadata.create_all(db_engine)
    with sessionmaker(db_engine)() as session:
        cache_repo = CoinbaseCacheRepository(session)
        client = _StubCoinbaseClient()
        client.accounts = [_account()]
        client.transactions = [_transaction()]
        clock = _StubClock(FIXED_NOW)
        service = CoinbaseService(
            cast(CoinbaseClient, client),
            cache_repo,
            now_fn=clock,
        )
        yield _ServiceTestContext(service=service, client=client, cache_repo=cache_repo, clock=clock)
    TransactionsCacheBase.metadata.drop_all(db_engine)


def test_budget_fetches_when_cache_is_empty(test_ctx: _ServiceTestContext) -> None:
    history = test_ctx.service.get_history(SyncMode.BUDGET)

    assert test_ctx.client.calls == [("fetch_accounts", None), ("fetch_transactions", "desc")]
    assert history.transaction_count == 1
    assert test_ctx.cache_repo.last_synced_at() == FIXED_NOW


def test_budget_skips_fetch_when_coinbase_history_was_synced_today(test_ctx: _ServiceTestContext) -> None:
    test_ctx.cache_repo.replace_history(
        fetched_at=FIXED_NOW.replace(hour=8),
        order="desc",
        accounts=test_ctx.client.accounts,
        transactions=test_ctx.client.transactions,
    )

    history = test_ctx.service.get_history(SyncMode.BUDGET)

    assert test_ctx.client.calls == []
    assert history.transaction_count == 1


def test_budget_fetches_when_last_sync_was_on_previous_day(test_ctx: _ServiceTestContext) -> None:
    test_ctx.cache_repo.replace_history(
        fetched_at=FIXED_NOW.replace(day=13, hour=23),
        order="desc",
        accounts=test_ctx.client.accounts,
        transactions=[_transaction("cached-tx")],
    )

    history = test_ctx.service.get_history(SyncMode.BUDGET)

    assert test_ctx.client.calls == [("fetch_accounts", None), ("fetch_transactions", "desc")]
    assert history.transactions[0].id == "tx-1"
    assert test_ctx.cache_repo.last_synced_at() == FIXED_NOW


def test_fresh_fetches_even_when_coinbase_history_was_synced_today(test_ctx: _ServiceTestContext) -> None:
    test_ctx.cache_repo.replace_history(
        fetched_at=FIXED_NOW.replace(hour=11),
        order="desc",
        accounts=test_ctx.client.accounts,
        transactions=[_transaction("cached-tx")],
    )

    history = test_ctx.service.get_history(SyncMode.FRESH)

    assert test_ctx.client.calls == [("fetch_accounts", None), ("fetch_transactions", "desc")]
    assert history.transactions[0].id == "tx-1"


def test_get_history_persists_full_coinbase_history_to_cache(test_ctx: _ServiceTestContext) -> None:
    older_transaction = _transaction("tx-1", "btc-wallet", created_at="2025-02-20T17:17:42Z")
    newer_transaction = _transaction("tx-2", "eth-wallet", created_at="2025-02-20T17:17:43Z")
    test_ctx.client.accounts = [_account("btc-wallet"), _account("eth-wallet")]
    test_ctx.client.transactions = [older_transaction, newer_transaction]

    history = test_ctx.service.get_history(SyncMode.FRESH)
    cached_history = test_ctx.cache_repo.load_history_payload()

    assert history.account_count == 2
    assert history.transaction_count == 2
    assert [tx["id"] for tx in cast(list[dict[str, Any]], cached_history["transactions"])] == [
        str(newer_transaction["id"]),
        str(older_transaction["id"]),
    ]
