from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from time import sleep
from typing import Any, Iterable, TypedDict, cast

from moralis import evm_api  # type: ignore

from accounts import DEFAULT_ACCOUNTS_PATH
from config import config
from db.transactions_cache import CACHE_DB_PATH, TransactionsCacheRepository, init_transactions_cache_db
from domain.ledger import ChainId, WalletAddress

logger = logging.getLogger(__name__)


class Account(TypedDict):
    address: WalletAddress
    chains: list[ChainId]


def _parse_block_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


class MoralisClient:
    # https://docs.moralis.com/
    def __init__(self, api_key: str, delay_seconds: float = 1.0):
        self.api_key = api_key
        self.delay_seconds = delay_seconds

    def fetch_transactions(
        self,
        chain: ChainId,
        address: WalletAddress,
        from_date: date | None = None,
    ) -> list[dict[str, Any]]:
        cursor: str | None = ""
        aggregated: list[dict[str, Any]] = []
        total = 0

        logger.info(
            "Fetching transactions chain=%s address=%s%s",
            chain,
            address,
            f" from_date={from_date:%Y-%m-%d}" if from_date else "",
        )

        while cursor is not None:
            params: dict[str, object] = {"chain": str(chain), "address": str(address)}
            if from_date:
                params["from_date"] = from_date.strftime("%Y-%m-%d")
            if cursor:
                params["cursor"] = cursor

            sleep(self.delay_seconds)
            response = evm_api.wallets.get_wallet_history(
                api_key=self.api_key,
                params=params,
            )
            cursor = response.get("cursor")

            batch = response.get("result", []) or []
            for entry in batch:
                # TODO: maybe add chain to other place this is low level Moralis client?
                aggregated.append({**entry, "chain": chain})
            total += len(batch)

            logger.info(
                "Fetched batch size=%d total=%d chain=%s address=%s",
                len(batch),
                total,
                chain,
                address,
            )

        return aggregated


class SyncMode(str, Enum):
    FRESH = "fresh"
    BUDGET = "budget"


class MoralisService:
    def __init__(
        self, client: MoralisClient, cache_repo: TransactionsCacheRepository, *, accounts_path: Path | None = None
    ):
        self.client = client
        self.cache = cache_repo
        self.accounts_path = accounts_path or DEFAULT_ACCOUNTS_PATH

    def _persist(self, chain: ChainId, records: Iterable[dict[str, Any]]) -> None:
        # TODO: there is property "chain": "optimism" in the record. Remove chain parameter
        rows: list[dict[str, object]] = []
        for record in records:
            block_timestamp = _parse_block_timestamp(str(record["block_timestamp"]))
            rows.append(
                {
                    "chain": str(chain),
                    "hash": str(record["hash"]),
                    "block_number": int(record["block_number"]),
                    "transaction_index": int(record["transaction_index"]),
                    "block_timestamp": block_timestamp,
                    "payload": json.dumps(record),
                }
            )

        self.cache.upsert_transactions(rows)

    def _ensure_chains_synced(self, mode: SyncMode) -> None:
        accounts = load_accounts(self.accounts_path)
        by_chain: dict[ChainId, list[WalletAddress]] = defaultdict(list)
        for account in accounts:
            for chain in account["chains"]:
                by_chain[chain].append(account["address"])

        yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)

        for chain, addresses in by_chain.items():
            last_synced_at = self.cache.last_synced_at(chain)
            should_fetch = mode == SyncMode.FRESH
            if mode == SyncMode.BUDGET and (last_synced_at is None or last_synced_at.date() < yesterday):
                should_fetch = True

            if not should_fetch:
                logger.info("Chain %s already synced; skipping fetch", chain)
                continue

            latest_block = self.cache.latest_block_timestamp(chain)
            api_from_date = (latest_block - timedelta(days=1)).date() if latest_block else None

            for address in addresses:
                self._sync_account_chain(chain, address, api_from_date)
            self.cache.mark_synced(chain, datetime.now(timezone.utc))

    def _sync_account_chain(self, chain: ChainId, address: WalletAddress, from_date: date | None) -> None:
        fetched = self.client.fetch_transactions(chain, address, from_date)
        self._persist(chain, fetched)

    def get_transactions(self, sync_mode: SyncMode | None = None) -> list[dict[str, Any]]:
        mode = sync_mode if sync_mode is not None else SyncMode.BUDGET
        self._ensure_chains_synced(mode)
        return self.cache.load_all_transactions()


def load_accounts(path: Path) -> list[Account]:
    raw = cast(list[dict[str, Any]], json.loads(path.read_text()))
    accounts: list[Account] = []
    for entry in raw:
        accounts.append(
            {
                "address": WalletAddress(entry["address"]),
                "chains": [ChainId(chain) for chain in entry["chains"]],
            }
        )
    return accounts


def build_default_service(cache_db: Path = CACHE_DB_PATH, accounts_path: Path | None = None) -> MoralisService:
    session = init_transactions_cache_db(db_file=cache_db)
    client = MoralisClient(api_key=config().moralis_api_key)
    cache_repo = TransactionsCacheRepository(session)
    return MoralisService(client, cache_repo, accounts_path=accounts_path)
