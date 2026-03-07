from __future__ import annotations

from collections.abc import Generator
from datetime import date, datetime, timedelta, timezone
from typing import NamedTuple, cast

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from accounts import AccountConfig
from clients.moralis import MoralisClient
from db.transactions_cache import TransactionsCacheBase, TransactionsCacheRepository
from domain.ledger import ChainId, WalletAddress
from services.moralis import MoralisService, SyncMode
from tests.constants import CHAIN, ETH_ADDRESS

FIXED_NOW = datetime(2026, 3, 7, 12, tzinfo=timezone.utc)


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


class _StubClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class _ServiceTestContext(NamedTuple):
    service: MoralisService
    client: _StubMoralisClient
    cache_repo: TransactionsCacheRepository
    clock: _StubClock


def _calls_as_tuples(calls: list[tuple[ChainId, WalletAddress, date | None]]) -> list[tuple[str, str, date | None]]:
    return [(str(chain), str(address), from_date) for chain, address, from_date in calls]


def _account(
    *,
    name: str = "Wallet",
    address: WalletAddress = ETH_ADDRESS,
    chains: frozenset[ChainId] = frozenset([CHAIN]),
    skip_sync: bool = False,
) -> AccountConfig:
    return AccountConfig(name=name, address=address, chains=chains, skip_sync=skip_sync)


@pytest.fixture()
def test_ctx(db_engine: Engine) -> Generator[_ServiceTestContext, None, None]:
    TransactionsCacheBase.metadata.create_all(db_engine)
    with sessionmaker(db_engine)() as session:
        cache_repo = TransactionsCacheRepository(session)
        client = _StubMoralisClient()
        clock = _StubClock(FIXED_NOW)
        service = MoralisService(
            cast(MoralisClient, client),
            cache_repo,
            accounts=[_account()],
            now_fn=clock,
        )
        yield _ServiceTestContext(service=service, client=client, cache_repo=cache_repo, clock=clock)
    TransactionsCacheBase.metadata.drop_all(db_engine)


def test_budget_fetches_new_wallet_chain_from_start_even_when_chain_has_recent_cursor(
    test_ctx: _ServiceTestContext,
) -> None:
    new_address = WalletAddress("0xddeeff")
    existing_cursor = FIXED_NOW - timedelta(hours=2)

    test_ctx.service.accounts = [
        _account(name="Existing"),
        _account(name="New", address=new_address),
    ]
    test_ctx.cache_repo.mark_synced(CHAIN, ETH_ADDRESS, existing_cursor)

    test_ctx.service.get_transactions(SyncMode.BUDGET)

    assert _calls_as_tuples(test_ctx.client.calls) == [(CHAIN, new_address, None)]
    assert test_ctx.cache_repo.last_synced_at(CHAIN, new_address) is not None


def test_budget_fetches_wallet_when_last_sync_was_on_previous_day(
    test_ctx: _ServiceTestContext,
) -> None:
    last_synced_1 = FIXED_NOW - timedelta(hours=23, minutes=59)
    last_synced_2 = FIXED_NOW - timedelta(days=1, hours=1)
    address_2 = WalletAddress("0xddeeff")

    test_ctx.service.accounts = [
        _account(name="Account 1"),
        _account(name="Account 2", address=address_2),
    ]

    expected_from_date = (last_synced_1 - timedelta(days=1)).date()
    test_ctx.cache_repo.mark_synced(CHAIN, ETH_ADDRESS, last_synced_1)
    test_ctx.cache_repo.mark_synced(CHAIN, address_2, last_synced_2)

    test_ctx.service.get_transactions(SyncMode.BUDGET)

    assert _calls_as_tuples(test_ctx.client.calls) == [
        (CHAIN, ETH_ADDRESS, expected_from_date),
        (CHAIN, address_2, expected_from_date),
    ]
    assert test_ctx.cache_repo.last_synced_at(CHAIN, ETH_ADDRESS) == FIXED_NOW
    assert test_ctx.cache_repo.last_synced_at(CHAIN, address_2) == FIXED_NOW


def test_budget_skips_wallet_chain_synced_today(test_ctx: _ServiceTestContext) -> None:
    last_synced_at = FIXED_NOW - timedelta(hours=1, minutes=59)
    test_ctx.cache_repo.mark_synced(CHAIN, ETH_ADDRESS, last_synced_at)

    test_ctx.service.get_transactions(SyncMode.BUDGET)

    assert test_ctx.client.calls == []


def test_budget_skips_wallet_marked_as_skip_sync(test_ctx: _ServiceTestContext) -> None:
    test_ctx.service.accounts = [_account(name="Dormant", skip_sync=True)]

    test_ctx.service.get_transactions(SyncMode.BUDGET)

    assert test_ctx.client.calls == []


def test_fresh_fetches_even_when_wallet_chain_was_recently_synced(test_ctx: _ServiceTestContext) -> None:
    recent_cursor = FIXED_NOW - timedelta(minutes=1)
    expected_from_date = (recent_cursor - timedelta(days=1)).date()
    test_ctx.cache_repo.mark_synced(CHAIN, ETH_ADDRESS, recent_cursor)

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

    test_ctx.client.set_transactions(chain=CHAIN, address=ETH_ADDRESS, transactions=[tx])

    transactions = test_ctx.service.get_transactions(SyncMode.FRESH)
    cached_transactions = test_ctx.cache_repo.load_all_transactions()

    assert _calls_as_tuples(test_ctx.client.calls) == [(CHAIN, ETH_ADDRESS, None)]
    assert len(transactions) == 1
    assert transactions[0]["chain"] == CHAIN
    assert transactions[0]["hash"] == tx["hash"]
    assert transactions[0]["block_number"] == tx["block_number"]
    assert len(cached_transactions) == 1
    assert cached_transactions[0]["chain"] == CHAIN
    assert cached_transactions[0]["hash"] == tx["hash"]
    assert cached_transactions[0]["block_number"] == tx["block_number"]
