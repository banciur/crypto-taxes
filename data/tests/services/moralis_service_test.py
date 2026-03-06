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


class _StubMoralisClient:
    def __init__(self) -> None:
        self.calls: list[tuple[ChainId, WalletAddress, date | None]] = []
        self.transactions_by_pair: dict[tuple[str, str], list[dict[str, object]]] = {}

    def set_transactions(
        self,
        *,
        chain: str,
        address: str,
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
        return self.transactions_by_pair.get((str(chain), str(address)), [])


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
    existing_address = "0xAABBcc"
    new_address = "0xdDeeff"
    shared_chain = "eth"
    existing_cursor = datetime.now(timezone.utc) - timedelta(hours=2)

    test_ctx.service.accounts = _accounts(
        [
            _account_entry(name="Existing", address=existing_address, chains=[shared_chain]),
            _account_entry(name="New", address=new_address, chains=[shared_chain]),
        ]
    )
    test_ctx.cache_repo.mark_synced(ChainId(shared_chain), WalletAddress(existing_address.lower()), existing_cursor)

    test_ctx.service.get_transactions(SyncMode.BUDGET)

    assert _calls_as_tuples(test_ctx.client.calls) == [(shared_chain, new_address.lower(), None)]
    assert test_ctx.cache_repo.last_synced_at(ChainId(shared_chain), WalletAddress(new_address.lower())) is not None


def test_budget_fetches_existing_wallet_chain_from_last_synced_cursor(test_ctx: _ServiceTestContext) -> None:
    address = "0xAbCdEf"
    chain = "arbitrum"

    stale_cursor = datetime.now(timezone.utc) - timedelta(days=3)
    expected_from_date = (stale_cursor - timedelta(days=1)).date()
    test_ctx.service.accounts = _accounts([_account_entry(name="Wallet", address=address, chains=[chain])])
    test_ctx.cache_repo.mark_synced(ChainId(chain), WalletAddress(address.lower()), stale_cursor)

    test_ctx.service.get_transactions(SyncMode.BUDGET)

    assert _calls_as_tuples(test_ctx.client.calls) == [(chain, address.lower(), expected_from_date)]
    refreshed_cursor = test_ctx.cache_repo.last_synced_at(ChainId(chain), WalletAddress(address.lower()))
    assert refreshed_cursor is not None
    assert refreshed_cursor.date() >= stale_cursor.date()


def test_budget_skips_recently_synced_wallet_chain(test_ctx: _ServiceTestContext) -> None:
    address = "0x1234ABCD"
    chain = "optimism"

    fresh_cursor = datetime.now(timezone.utc) - timedelta(hours=6)
    test_ctx.service.accounts = _accounts([_account_entry(name="Wallet", address=address, chains=[chain])])
    test_ctx.cache_repo.mark_synced(ChainId(chain), WalletAddress(address.lower()), fresh_cursor)

    test_ctx.service.get_transactions(SyncMode.BUDGET)

    assert test_ctx.client.calls == []


def test_budget_skips_wallet_chain_synced_yesterday(test_ctx: _ServiceTestContext) -> None:
    address = "0xAAAABBBB"
    chain = "base"

    yesterday_cursor = datetime.now(timezone.utc) - timedelta(days=1, hours=1)
    test_ctx.service.accounts = _accounts([_account_entry(name="Wallet", address=address, chains=[chain])])
    test_ctx.cache_repo.mark_synced(ChainId(chain), WalletAddress(address.lower()), yesterday_cursor)

    test_ctx.service.get_transactions(SyncMode.BUDGET)

    assert test_ctx.client.calls == []


def test_budget_skips_wallet_marked_as_skip_sync(test_ctx: _ServiceTestContext) -> None:
    address = "0x55AA66BB"
    chain = "eth"

    test_ctx.service.accounts = _accounts(
        [_account_entry(name="Dormant", address=address, chains=[chain], skip_sync=True)]
    )

    test_ctx.service.get_transactions(SyncMode.BUDGET)

    assert test_ctx.client.calls == []


def test_fresh_fetches_even_when_wallet_chain_was_recently_synced(test_ctx: _ServiceTestContext) -> None:
    address = "0xAA11BB22"
    chain = "eth"

    recent_cursor = datetime.now(timezone.utc) - timedelta(hours=3)
    expected_from_date = (recent_cursor - timedelta(days=1)).date()
    test_ctx.service.accounts = _accounts([_account_entry(name="Wallet", address=address, chains=[chain])])
    test_ctx.cache_repo.mark_synced(ChainId(chain), WalletAddress(address.lower()), recent_cursor)

    test_ctx.service.get_transactions(SyncMode.FRESH)

    assert _calls_as_tuples(test_ctx.client.calls) == [(chain, address.lower(), expected_from_date)]


def test_get_transactions_persists_fetched_transactions(test_ctx: _ServiceTestContext) -> None:
    address = "0xC0FFEE"
    chain = "arbitrum"
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

    test_ctx.service.accounts = _accounts([_account_entry(name="Wallet", address=address, chains=[chain])])
    test_ctx.client.set_transactions(chain=chain, address=address.lower(), transactions=[tx])

    transactions = test_ctx.service.get_transactions(SyncMode.FRESH)

    assert _calls_as_tuples(test_ctx.client.calls) == [(chain, address.lower(), None)]
    assert len(transactions) == 1
    assert transactions[0]["chain"] == chain
    assert transactions[0]["hash"] == tx["hash"]
    assert transactions[0]["block_number"] == tx["block_number"]
