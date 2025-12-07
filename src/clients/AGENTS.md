# On-chain transactions via Moralis (with caching)

- Quick orientation for the on-chain transaction fetcher implemented through the Moralis service. Primary goal: get wallet transactions; caching to avoid redundant API calls (service is not free). `doc/CURRENT.md` includes a system overview (domain + this component); treat that as the canonical big-picture reference.
- Entry point: `MoralisService.get_transactions(mode: SyncMode | None = None)`. Loads accounts from `accounts_path` (default `data/accounts.json`), ensures chains are synced per mode, then returns all cached transactions ordered in DB.
- Modes: `FRESH` always fetches `(latest_cached_date - 1 day)` → now; `BUDGET` only fetches if per-chain `last_synced_at` is missing or older than yesterday. Empty cache fetches all (no `from_date`); overlap uses `(latest_cached_date - 1 day)` when present.
- Sync: chain-scoped freshness check; if a chain needs refresh, fetch for every account listing that chain. Unique `(chain, hash)` dedupes repeats.
- Fetching: `MoralisClient.fetch_transactions(chain, address, from_date?)`, 1s delay per page, logs batch sizes/totals; results keep Moralis order; `chain` added to each record.
- Persistence: SQLite `data/transactions_cache.db` via `TransactionsCacheRepository`
- Script: `scripts/fetch_wallet_history.py` accepts `--mode` and `--accounts`, syncs, prints last 5 transactions; storage is in DB (no file dump).
- Types: `ChainId`/`WalletAddress` are `NewType(str, ...)`; accounts are `{"address": ..., "chains": [...]}`.
