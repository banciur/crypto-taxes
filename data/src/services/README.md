# Services

## Moralis service
- Fetches data for all tracked accounts storing them in the cache along the way.
- Accounts with `skip_sync=true` are excluded from fetches.
- Cache uses SQLite persistence.
- Raw cache implementation lives in `db/tx_cache_moralis.py`.
- Helper scripts live under `scripts/moralis/`.

## Coinbase service
- Owns Coinbase fetch/cache decisions and loads Coinbase Track account history through `CoinbaseCacheRepository`.
- Raw cache implementation lives in `db/tx_cache_coinbase.py`.
- Uses the same `SyncMode` enum as Moralis:
  - `BUDGET`: fetch at most once per UTC day for the whole Coinbase source;
  - `FRESH`: always fetch full Coinbase history.
- Coinbase sync is intentionally whole-snapshot; unlike Moralis there is no per-wallet checkpointing logic.

### Sync modes
- `FRESH`: always fetches every configured account/location pair using overlap from that pair's sync checkpoint (`last_synced_at - 1 day`).
- `BUDGET`: fetches at most once per UTC day for each account/location pair, so repeated runs on the same UTC day do not trigger extra Moralis API calls.

### Sync behavior
- Sync checkpoints/freshness are tracked per account/location pair (`location + address`).
- Missing checkpoint means first-time backfill (`from_date` omitted).
