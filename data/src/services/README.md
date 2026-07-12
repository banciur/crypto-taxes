# Services

## Price services

- `PriceService` (`price_service.py`) implements the domain `PriceProvider`, resolving `base -> quote`
  as a cross-rate through a single numeraire pivot (USD) and caching directional edges.
- Stablecoins are valued via the fiat currency they are pegged to (peg target matters: EUR-pegged
  stables are not worth 1 USD).
- An asset listed in `ASSETS_PRICED_AS` takes another asset's price 1:1 (rETH2 takes ETH's). The
  substitution happens on both sides of the pair before the cache is consulted, so such an asset is
  never cached, never fetched, and needs no `cmc_asset_map.json` entry. Keep this table separate
  from `STABLE_ASSETS_BY_PEG`: that one feeds the `STABLE` `ValuationTier`, and a priced-as asset
  must stay a normal `MARKET`-tier, FIFO-tracked asset that merely borrows a rate.
- `PriceResolver` (`price_resolver.py`) only routes a fetch to the owning provider: fiat to Open
  Exchange Rates, everything else to CoinMarketCap.
- Config (numeraire, fiat codes, stable pegs) comes from `config` constants; the cache is SQLite
  (`src/db/price_cache.py`). The pricing contract lives in `src/domain/pricing.py`, provider
  clients in `src/clients/`.

## Moralis service
- Fetches data for real accounts, storing fetched transactions in the cache along the way.
- Real accounts with `skip_sync=true` are excluded from fetches.
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
