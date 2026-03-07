# Services

## Moralis service
- Fetches data for all tracked accounts storing them in the cache along the way.
- Accounts with `skip_sync=true` are excluded from fetches.
- Cache uses SQLite persistence.
- Helper scripts live under `scripts/moralis/`.

### Sync modes
- `FRESH`: always fetches every configured account/chain pair using overlap from that pair's sync checkpoint (`last_synced_at - 1 day`).
- `BUDGET`: fetches at most once per UTC day for each account/chain pair, so repeated runs on the same UTC day do not trigger extra Moralis API calls.

### Sync behavior
- Sync checkpoints/freshness are tracked per account/chain pair (`chain + address`).
- Missing checkpoint means first-time backfill (`from_date` omitted).
