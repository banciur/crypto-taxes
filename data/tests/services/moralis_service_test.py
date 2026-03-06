from __future__ import annotations

from collections.abc import Generator, Sequence
from datetime import date, datetime, timedelta, timezone
from typing import NamedTuple, cast

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from accounts import AccountConfig
from clients.moralis import MoralisClient
from db.transactions_cache import TransactionsCacheBase, TransactionsCacheRepository
from domain.ledger import ChainId, WalletAddress
from services.moralis import MoralisService, SyncMode
from tests.constants import CHAIN, ETH_ADDRESS


class _StubMoralisClient:
    def __init__(self) -> None:
        self.calls: list[tuple[ChainId, WalletAddress, date | None]] = []
        self.transactions_by_pair: dict[tuple[ChainId, WalletAddress], list[dict[str, object]]] = {}

    def set_transactions(
        self,
        *,
        chain: ChainId,
        address: WalletAddress,
        transactions: list[dict[str, object]],
    ) -> None:
        self.transactions_by_pair[(chain, address)] = transactions

    def fetch_transactions(
        self,
        chain: ChainId,
        address: WalletAddress,
        from_date: date | None = None,
    ) -> list[dict[str, object]]:
        self.calls.append((chain, address, from_date))
        return self.transactions_by_pair.get((chain, address), [])


class _ServiceTestContext(NamedTuple):
    service: MoralisService
    client: _StubMoralisClient
    cache_repo: TransactionsCacheRepository


@pytest.fixture()
def cache_session(db_engine: Engine) -> Generator[Session, None, None]:
    TransactionsCacheBase.metadata.create_all(db_engine)
    with sessionmaker(db_engine)() as session:
        yield session
    TransactionsCacheBase.metadata.drop_all(db_engine)


@pytest.fixture()
def test_ctx(cache_session: Session) -> _ServiceTestContext:
    cache_repo = TransactionsCacheRepository(cache_session)
    client = _StubMoralisClient()
    service = MoralisService(
        cast(MoralisClient, client),
        cache_repo,
        accounts=[],
    )
    return _ServiceTestContext(service=service, client=client, cache_repo=cache_repo)


def _account_entry(
    *,
    name: str,
    address: str,
    chains: list[str],
    skip_sync: bool = False,
) -> dict[str, object]:
    return {
        "name": name,
        "address": address,
        "chains": chains,
        "skip_sync": skip_sync,
    }


def _accounts(account_entries: Sequence[dict[str, object]]) -> list[AccountConfig]:
    return [AccountConfig.model_validate(entry) for entry in account_entries]


def _calls_as_tuples(calls: list[tuple[ChainId, WalletAddress, date | None]]) -> list[tuple[str, str, date | None]]:
    return [(str(chain), str(address), from_date) for chain, address, from_date in calls]


def test_budget_fetches_new_wallet_chain_from_start_even_when_chain_has_recent_cursor(
    test_ctx: _ServiceTestContext,
) -> None:
    new_address = "0xddeeff"
    existing_cursor = datetime.now(timezone.utc) - timedelta(hours=2)

    test_ctx.service.accounts = _accounts(
        [
            _account_entry(name="Existing", address=ETH_ADDRESS, chains=[CHAIN]),
            _account_entry(name="New", address=new_address, chains=[CHAIN]),
        ]
    )
    test_ctx.cache_repo.mark_synced(ChainId(CHAIN), WalletAddress(ETH_ADDRESS), existing_cursor)

    test_ctx.service.get_transactions(SyncMode.BUDGET)

    assert _calls_as_tuples(test_ctx.client.calls) == [(CHAIN, new_address.lower(), None)]
    assert test_ctx.cache_repo.last_synced_at(ChainId(CHAIN), WalletAddress(new_address)) is not None


def test_budget_fetches_existing_wallet_chain_from_last_synced_cursor(test_ctx: _ServiceTestContext) -> None:
    stale_cursor = datetime.now(timezone.utc) - timedelta(days=3)
    expected_from_date = (stale_cursor - timedelta(days=1)).date()
    test_ctx.service.accounts = _accounts([_account_entry(name="Wallet", address=ETH_ADDRESS, chains=[CHAIN])])
    test_ctx.cache_repo.mark_synced(ChainId(CHAIN), ETH_ADDRESS, stale_cursor)

    test_ctx.service.get_transactions(SyncMode.BUDGET)

    assert _calls_as_tuples(test_ctx.client.calls) == [(CHAIN, ETH_ADDRESS, expected_from_date)]
    refreshed_cursor = test_ctx.cache_repo.last_synced_at(ChainId(CHAIN), ETH_ADDRESS)
    assert refreshed_cursor is not None
    assert refreshed_cursor.date() >= stale_cursor.date()


def test_budget_skips_recently_synced_wallet_chain(test_ctx: _ServiceTestContext) -> None:
    fresh_cursor = datetime.now(timezone.utc) - timedelta(hours=6)
    test_ctx.service.accounts = _accounts([_account_entry(name="Wallet", address=ETH_ADDRESS, chains=[CHAIN])])
    test_ctx.cache_repo.mark_synced(ChainId(CHAIN), ETH_ADDRESS, fresh_cursor)

    test_ctx.service.get_transactions(SyncMode.BUDGET)

    assert test_ctx.client.calls == []


def test_budget_skips_wallet_chain_synced_yesterday(test_ctx: _ServiceTestContext) -> None:
    yesterday_cursor = datetime.now(timezone.utc) - timedelta(days=1, hours=1)
    test_ctx.service.accounts = _accounts([_account_entry(name="Wallet", address=ETH_ADDRESS, chains=[CHAIN])])
    test_ctx.cache_repo.mark_synced(ChainId(CHAIN), ETH_ADDRESS, yesterday_cursor)

    test_ctx.service.get_transactions(SyncMode.BUDGET)

    assert test_ctx.client.calls == []


def test_budget_skips_wallet_marked_as_skip_sync(test_ctx: _ServiceTestContext) -> None:
    test_ctx.service.accounts = _accounts(
        [_account_entry(name="Dormant", address=ETH_ADDRESS, chains=[CHAIN], skip_sync=True)]
    )

    test_ctx.service.get_transactions(SyncMode.BUDGET)

    assert test_ctx.client.calls == []


def test_fresh_fetches_even_when_wallet_chain_was_recently_synced(test_ctx: _ServiceTestContext) -> None:
    recent_cursor = datetime.now(timezone.utc) - timedelta(hours=3)
    expected_from_date = (recent_cursor - timedelta(days=1)).date()
    test_ctx.service.accounts = _accounts([_account_entry(name="Wallet", address=ETH_ADDRESS, chains=[CHAIN])])
    test_ctx.cache_repo.mark_synced(ChainId(CHAIN), ETH_ADDRESS, recent_cursor)

    test_ctx.service.get_transactions(SyncMode.FRESH)

    assert _calls_as_tuples(test_ctx.client.calls) == [(CHAIN, ETH_ADDRESS, expected_from_date)]


def test_get_transactions_persists_fetched_transactions(test_ctx: _ServiceTestContext) -> None:
    tx: dict[str, object] = {
        "hash": "0xhash",
        "block_number": "123",
        "transaction_index": "4",
        "block_timestamp": "2025-05-16T05:04:40.000Z",
        "from_address": "0xfrom",
        "native_transfers": [],
        "erc20_transfers": [],
        "transaction_fee": "0",
    }

    test_ctx.service.accounts = _accounts([_account_entry(name="Wallet", address=ETH_ADDRESS, chains=[CHAIN])])
    test_ctx.client.set_transactions(chain=CHAIN, address=ETH_ADDRESS, transactions=[tx])

    transactions = test_ctx.service.get_transactions(SyncMode.FRESH)

    assert _calls_as_tuples(test_ctx.client.calls) == [(CHAIN, ETH_ADDRESS, None)]
    assert len(transactions) == 1
    assert transactions[0]["chain"] == CHAIN
    assert transactions[0]["hash"] == tx["hash"]
    assert transactions[0]["block_number"] == tx["block_number"]
