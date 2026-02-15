# On-chain transactions via Moralis (with caching)

- Quick orientation for the on-chain transaction fetcher implemented through the Moralis service. Primary goal: get wallet transactions; caching to avoid redundant API calls (service is not free). `doc/CURRENT.md` includes a system overview (domain + this component); treat that as the canonical big-picture reference.

## Client/caching
- Entry point: `MoralisService.get_transactions(mode: SyncMode | None = None)`. Loads accounts from `accounts_path` (default `artifacts/accounts.json`), ensures chains are synced per mode, then returns all cached transactions ordered in DB.
- Modes: `FRESH` always fetches for every configured account/chain pair using overlap from that pair's cursor (`last_synced_at - 1 day`); `BUDGET` fetches only account/chain pairs with missing cursor or cursor older than yesterday.
- Sync: freshness and cursors are tracked per account/chain pair (`chain + address`). Missing cursor means first-time backfill (`from_date` omitted), so newly added wallets sync from start.
- Fetching: `MoralisClient.fetch_transactions(chain, address, from_date?)`, 1s delay per page, logs batch sizes/totals; results keep Moralis order; `chain` added to each record.
- Persistence: SQLite `artifacts/transactions_cache.db` via `TransactionsCacheRepository`
- Script: `scripts/fetch_wallet_history.py` accepts `--mode` and `--accounts`, syncs, prints last 5 transactions; storage is in DB (no file dump).
- Types: `ChainId`/`WalletAddress` are `NewType(str, ...)`; accounts are `{"name": ..., "address": ..., "chains": [...], "skip_sync": ...}`.
- Sync filter: accounts with `skip_sync=true` are excluded from Moralis fetches but remain valid tracked wallets for parsing cached transactions.

## Moralis → LedgerEvent parsing (current)
- Parsing rules live in `data/src/importers/moralis/README.md`.
