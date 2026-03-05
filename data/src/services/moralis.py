from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path

from accounts import load_accounts
from clients.moralis import MoralisClient
from config import ACCOUNTS_PATH, TRANSACTIONS_CACHE_DB_PATH, config
from db.transactions_cache import (
    TransactionRow,
    TransactionsCacheRepository,
    init_transactions_cache_db,
)
from domain.ledger import ChainId
from type_defs import RawTxs

logger = logging.getLogger(__name__)


def _parse_block_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


class SyncMode(str, Enum):
    FRESH = "fresh"
    BUDGET = "budget"


class MoralisService:
    def __init__(
        self, client: MoralisClient, cache_repo: TransactionsCacheRepository, *, accounts_path: Path | None = None
    ):
        self.client = client
        self.cache = cache_repo
        self.accounts_path = accounts_path or ACCOUNTS_PATH

    def _persist(self, chain: ChainId, records: RawTxs) -> None:
        rows: list[TransactionRow] = [
            {
                "chain": chain,
                "hash": str(record["hash"]),
                "block_number": int(record["block_number"]),
                "transaction_index": int(record["transaction_index"]),
                "block_timestamp": _parse_block_timestamp(str(record["block_timestamp"])),
                "payload": json.dumps(record),
            }
            for record in records
        ]

        self.cache.upsert_transactions(rows)

    def _ensure_chains_synced(self, mode: SyncMode) -> None:
        yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)

        for account in load_accounts(self.accounts_path):
            if account.skip_sync:
                logger.info("Address %s (%s) is marked skip_sync; skipping fetch", account.address, account.name)
                continue
            address = account.address
            for chain in account.chains:
                last_synced_at = self.cache.last_synced_at(chain, address)
                should_fetch = mode == SyncMode.FRESH
                if mode == SyncMode.BUDGET and (last_synced_at is None or last_synced_at.date() < yesterday):
                    should_fetch = True

                if not should_fetch:
                    logger.info("Address %s on chain %s already synced; skipping fetch", address, chain)
                    continue

                from_date = (last_synced_at - timedelta(days=1)).date() if last_synced_at else None
                txs = self.client.fetch_transactions(chain, address, from_date)
                self._persist(chain, txs)
                self.cache.mark_synced(chain, address, datetime.now(timezone.utc))

    def get_transactions(self, sync_mode: SyncMode | None = None) -> RawTxs:
        mode = sync_mode if sync_mode is not None else SyncMode.BUDGET
        self._ensure_chains_synced(mode)
        return self.cache.load_all_transactions()


def build_default_service(
    cache_db: Path = TRANSACTIONS_CACHE_DB_PATH, accounts_path: Path | None = None
) -> MoralisService:
    session = init_transactions_cache_db(db_path=cache_db)
    client = MoralisClient(api_key=config().moralis_api_key)
    cache_repo = TransactionsCacheRepository(session)
    return MoralisService(client, cache_repo, accounts_path=accounts_path)
