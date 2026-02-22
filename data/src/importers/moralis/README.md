# Moralis importer

- Purpose: fetch on-chain transactions via `MoralisService.get_transactions` and translate them into `LedgerEvent`s.
- Scope (current): ERC20 and native transfers; NFT transfers are ignored.
- Flow:
  - Fetch transactions with `SyncMode` (fresh/budget) through `MoralisService` (uses `accounts_path` for accounts).
  - For each tx, map `chain` to `EventLocation` (eth/arbitrum/optimism/base supported); skip unknown chains or missing hashes.
  - Build legs from `native_transfers` and `erc20_transfers` only for owned accounts resolved by `AccountRegistry`; unknown counterparties are ignored.
  - Owned leg `account_chain_id` is chain-scoped (`{chain}:{address}`), e.g. `eth:0xabc...`.
  - Add a fee leg from `transaction_fee` when tx sender resolves to an owned account (`ETH`, `is_fee=True`).
  - Event emission: emit an event when there is at least one owned leg; otherwise skip tx.
- Notes: addresses normalized to lowercase; results sorted by timestamp. Caching is handled in `MoralisService`/`TransactionsCacheRepository`.
