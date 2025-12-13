# On-chain transactions via Moralis (with caching)

- Quick orientation for the on-chain transaction fetcher implemented through the Moralis service. Primary goal: get wallet transactions; caching to avoid redundant API calls (service is not free). `doc/CURRENT.md` includes a system overview (domain + this component); treat that as the canonical big-picture reference.

## Client/caching
- Entry point: `MoralisService.get_transactions(mode: SyncMode | None = None)`. Loads accounts from `accounts_path` (default `artifacts/accounts.json`), ensures chains are synced per mode, then returns all cached transactions ordered in DB.
- Modes: `FRESH` always fetches `(latest_cached_date - 1 day)` → now; `BUDGET` only fetches if per-chain `last_synced_at` is missing or older than yesterday. Empty cache fetches all (no `from_date`); overlap uses `(latest_cached_date - 1 day)` when present.
- Sync: chain-scoped freshness check; if a chain needs refresh, fetch for every account listing that chain. Unique `(chain, hash)` dedupes repeats.
- Fetching: `MoralisClient.fetch_transactions(chain, address, from_date?)`, 1s delay per page, logs batch sizes/totals; results keep Moralis order; `chain` added to each record.
- Persistence: SQLite `artifacts/transactions_cache.db` via `TransactionsCacheRepository`
- Script: `scripts/fetch_wallet_history.py` accepts `--mode` and `--accounts`, syncs, prints last 5 transactions; storage is in DB (no file dump).
- Types: `ChainId`/`WalletAddress` are `NewType(str, ...)`; accounts are `{"address": ..., "chains": [...]}`.

## Moralis → LedgerEvent parsing (current)
- Inputs: cached transaction payloads from `get_transactions` (include added `chain`), wallet addresses from `artifacts/accounts.json` (lowercased for matching).
- Event envelope: one `LedgerEvent` per tx hash; `timestamp` from `block_timestamp` (UTC); `ingestion="moralis"`; `origin_external_id`=hash; `origin_location` via chain→EventLocation map.
- Transfers handled now: ERC20 transfers only (asset id = contract). NFT and native transfers are ignored in the current implementation. Outgoing if `from_address` is ours and `to_address` not ours; incoming if `to_address` is ours and `from_address` not ours.
- Self transfers: if a transaction has both outgoing and incoming involving our wallets, treat the whole tx as a trade (emit both legs accordingly).
- EventType (current ERC20-only handling): if both incoming and outgoing transfers → `TRADE`; only incoming → `REWARD`; only outgoing → `WITHDRAWAL`. If no transfers/legs, drop the tx (native/NFT not yet parsed; OPERATION will be used when native handling is added).
- Asset mapping: native asset per chain (ETH for ethereum, arbitrum, optimism, base). ERC20 decimals from `token_decimals` to scale `value`/`value_formatted` into `Decimal`.
- Quantities: use `value_formatted` when present, else `Decimal(value)`; always `Decimal`.
- Normalize addresses lower-case for comparisons; keep payload in cache for traceability.
