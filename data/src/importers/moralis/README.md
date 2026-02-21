# Moralis importer

- Purpose: fetch on-chain transactions via `MoralisService.get_transactions` and translate them into `LedgerEvent`s.
- Scope (current): ERC20 and native transfers; NFT transfers are ignored.
- Flow:
  - Fetch transactions with `SyncMode` (fresh/budget) through `MoralisService` (uses `accounts_path` for wallets).
  - For each tx, map `chain` to `EventLocation` (eth/arbitrum/optimism/base supported); skip unknown chains or missing hashes.
  - Build legs from `native_transfers`: outgoing if `from_address` is ours; incoming if `to_address` is ours; self transfers emit both legs. Dedupe internal/external duplicates; asset_id is always `ETH` (asserts if different).
  - Build legs from `erc20_transfers`: outgoing if `from_address` is ours; incoming if `to_address` is ours; self transfers emit both legs. Quantities use `value_formatted` (must be finite), otherwise only raw `value` with missing `token_decimals` is accepted; asset_id = contract address lowercased.
  - Add a fee leg from `transaction_fee` when `from_address` is ours (ETH, `is_fee=True`).
  - Event emission: emit an event when there is at least one incoming leg, outgoing leg, or an own-wallet fee leg; otherwise skip tx.
- Notes: addresses normalized to lowercase; results sorted by timestamp. Caching is handled in `MoralisService`/`TransactionsCacheRepository`.
