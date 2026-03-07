from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Sequence

from accounts import AccountConfig
from clients.moralis import MoralisClient
from db.transactions_cache import (
    TransactionRow,
    TransactionsCacheRepository,
)
from domain.ledger import ChainId
from type_defs import RawTxs
from utils.misc import utc_now

logger = logging.getLogger(__name__)


def _parse_block_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


class SyncMode(str, Enum):
    FRESH = "fresh"
    BUDGET = "budget"


class MoralisService:
    def __init__(
        self,
        client: MoralisClient,
        cache_repo: TransactionsCacheRepository,
        accounts: Sequence[AccountConfig],
        now_fn: Callable[[], datetime] = utc_now,
    ):
        self.client = client
        self.cache = cache_repo
        self.accounts = accounts
        self._now = now_fn

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
        for account in self.accounts:
            if account.skip_sync:
                logger.info("Address %s (%s) is marked skip_sync; skipping fetch", account.address, account.name)
                continue
            address = account.address
            for chain in account.chains:
                last_synced_at = self.cache.last_synced_at(chain, address)
                should_fetch = mode == SyncMode.FRESH
                if mode == SyncMode.BUDGET and (last_synced_at is None or last_synced_at.date() < self._now().date()):
                    should_fetch = True

                if not should_fetch:
                    logger.info("Address %s on chain %s already synced; skipping fetch", address, chain)
                    continue

                from_date = (last_synced_at - timedelta(days=1)).date() if last_synced_at else None
                txs = self.client.fetch_transactions(chain, address, from_date)
                self._persist(chain, txs)
                self.cache.mark_synced(chain, address, self._now())

    def get_transactions(self, sync_mode: SyncMode = SyncMode.BUDGET) -> RawTxs:
        self._ensure_chains_synced(sync_mode)
        return self.cache.load_all_transactions()
