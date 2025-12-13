# Moralis importer

- Purpose: fetch on-chain transactions via `MoralisService.get_transactions` and translate them into `LedgerEvent`s.
- Scope (current): ERC20 transfers only; native and NFT transfers are ignored for now.
- Flow:
  - Fetch transactions with `SyncMode` (fresh/budget) through `MoralisService` (uses `accounts_path` for wallets).
  - For each tx, map `chain` to `EventLocation` (eth/arbitrum/optimism/base supported); skip unknown chains or missing hashes.
  - Build legs from `erc20_transfers`: outgoing if `from_address` is ours; incoming if `to_address` is ours; self transfers emit both legs. Quantities use `value_formatted` when present, else `value` scaled by `token_decimals`; asset_id = contract address lowercased.
  - EventType: both in/out → `TRADE`; only in → `REWARD`; only out → `WITHDRAWAL`; no transfers but `from_address` is ours → `OPERATION`; otherwise skip tx.
  - Ingestion tag: `"moralis"`.
- Notes: addresses normalized to lowercase; results sorted by timestamp. Caching is handled in `MoralisService`/`TransactionsCacheRepository`.
