# Services

## Moralis service (sync + caching)
- Service entry point: `services.moralis.MoralisService.get_transactions(mode: SyncMode | None = None)`.
- Responsibility: load configured accounts, decide what to sync by mode/cursor, fetch via `MoralisClient`, persist into transaction cache, then return cached transactions.
- Default accounts source: `artifacts/accounts.json` (`accounts_path` override supported).

### Sync modes
- `FRESH`: always fetches every configured account/chain pair using overlap from that pair's cursor (`last_synced_at - 1 day`).
- `BUDGET`: fetches only account/chain pairs with missing cursor or with cursor older than yesterday.

### Sync behavior
- Cursors/freshness are tracked per account/chain pair (`chain + address`).
- Missing cursor means first-time backfill (`from_date` omitted).
- Accounts with `skip_sync=true` are excluded from Moralis fetches.

### Storage and script
- Persistence: SQLite `artifacts/transactions_cache.db` through `TransactionsCacheRepository`.
- Script: `scripts/moralis/fetch_wallet_history.py` accepts `--mode` and `--accounts`, performs sync, then prints the last five cached transactions.
- Moralis helper scripts live under `scripts/moralis/`:
  - `cache_lookup.py` inspects cached rows by id/hash.
  - `client_fetch.py` calls `MoralisClient` directly and prints raw Moralis payloads.

### Types and related docs
- `ChainId` and `WalletAddress` are domain types used by client/service boundaries.
- Moralis parsing into domain events is documented in `data/src/importers/moralis/README.md`.
