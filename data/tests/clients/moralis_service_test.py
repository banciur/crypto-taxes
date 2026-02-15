from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import cast

from clients.moralis import MoralisClient, MoralisService, SyncMode
from db.transactions_cache import TransactionsCacheRepository
from domain.ledger import ChainId, WalletAddress


class _StubMoralisClient:
    def __init__(self) -> None:
        self.calls: list[tuple[ChainId, WalletAddress, date | None]] = []

    def fetch_transactions(
        self,
        chain: ChainId,
        address: WalletAddress,
        from_date: date | None = None,
    ) -> list[dict[str, object]]:
        self.calls.append((chain, address, from_date))
        return []


class _StubTransactionsCache:
    def __init__(self, *, last_synced: dict[tuple[str, str], datetime | None] | None = None) -> None:
        self.last_synced = last_synced or {}
        self.marked_synced: list[tuple[ChainId, WalletAddress, datetime]] = []

    def upsert_transactions(self, records: list[dict[str, object]]) -> None:
        return None

    def load_all_transactions(self) -> list[dict[str, object]]:
        return []

    def last_synced_at(self, chain: ChainId, address: WalletAddress) -> datetime | None:
        return self.last_synced.get((str(chain), str(address)))

    def mark_synced(self, chain: ChainId, address: WalletAddress, when: datetime) -> None:
        self.last_synced[(str(chain), str(address))] = when
        self.marked_synced.append((chain, address, when))


def _write_accounts(path: Path, *, entries: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(entries))


def _calls_as_tuples(calls: list[tuple[ChainId, WalletAddress, date | None]]) -> list[tuple[str, str, date | None]]:
    return [(str(chain), str(address), from_date) for chain, address, from_date in calls]


def test_budget_fetches_new_wallet_chain_from_start_even_when_chain_has_recent_cursor(tmp_path: Path) -> None:
    existing_address = "0xAABBcc"
    new_address = "0xdDeeff"
    shared_chain = "eth"
    accounts_path = tmp_path / "accounts.json"
    _write_accounts(
        accounts_path,
        entries=[
            {"address": existing_address, "chains": [shared_chain]},
            {"address": new_address, "chains": [shared_chain]},
        ],
    )

    now = datetime.now(timezone.utc)
    existing_cursor = now - timedelta(hours=2)
    cache = _StubTransactionsCache(
        last_synced={
            (shared_chain, existing_address.lower()): existing_cursor,
        }
    )
    client = _StubMoralisClient()
    service = MoralisService(
        cast(MoralisClient, client),
        cast(TransactionsCacheRepository, cache),
        accounts_path=accounts_path,
    )

    service.get_transactions(SyncMode.BUDGET)

    assert _calls_as_tuples(client.calls) == [(shared_chain, new_address.lower(), None)]


def test_budget_fetches_existing_wallet_chain_from_last_synced_cursor(tmp_path: Path) -> None:
    address = "0xAbCdEf"
    chain = "arbitrum"
    accounts_path = tmp_path / "accounts.json"
    _write_accounts(accounts_path, entries=[{"address": address, "chains": [chain]}])

    now = datetime.now(timezone.utc)
    stale_cursor = now - timedelta(days=3)
    expected_from_date = (stale_cursor - timedelta(days=1)).date()
    cache = _StubTransactionsCache(last_synced={(chain, address.lower()): stale_cursor})
    client = _StubMoralisClient()
    service = MoralisService(
        cast(MoralisClient, client),
        cast(TransactionsCacheRepository, cache),
        accounts_path=accounts_path,
    )

    service.get_transactions(SyncMode.BUDGET)

    assert _calls_as_tuples(client.calls) == [(chain, address.lower(), expected_from_date)]
    assert len(cache.marked_synced) == 1
    marked_chain, marked_address, _ = cache.marked_synced[0]
    assert str(marked_chain) == chain
    assert str(marked_address) == address.lower()


def test_budget_skips_recently_synced_wallet_chain(tmp_path: Path) -> None:
    address = "0x1234ABCD"
    chain = "optimism"
    accounts_path = tmp_path / "accounts.json"
    _write_accounts(accounts_path, entries=[{"address": address, "chains": [chain]}])

    now = datetime.now(timezone.utc)
    fresh_cursor = now - timedelta(hours=6)
    cache = _StubTransactionsCache(last_synced={(chain, address.lower()): fresh_cursor})
    client = _StubMoralisClient()
    service = MoralisService(
        cast(MoralisClient, client),
        cast(TransactionsCacheRepository, cache),
        accounts_path=accounts_path,
    )

    service.get_transactions(SyncMode.BUDGET)

    assert client.calls == []
    assert cache.marked_synced == []
