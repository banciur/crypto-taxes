# Moralis importer

- Purpose: fetch on-chain transactions via `MoralisService.get_transactions` and translate them into `LedgerEvent`s.
- Scope: ERC20 and native transfers; NFT transfers are ignored.
- Flow:
  - Fetch transactions through `MoralisService` which caches them using `MoralisCacheRepository`.
  - Build legs from `native_transfers` and `erc20_transfers` only for owned accounts, unknown counterparties are ignored.
  - Collapse legs by (`asset_id`, `account_chain_id`, `is_fee`) inside each transaction so same-token round-trips net to one leg.
  - Add a fee leg from `transaction_fee` when tx sender resolves to an owned account (`ETH`, `is_fee=True`).
  - Event emission: emit an event when there is at least one owned leg; otherwise skip tx.
  - Automatic spam persistence: when a transaction emits an event and Moralis sets `possible_spam=true`, the importer writes an `AUTO_MORALIS` spam correction. It uses `skip_if_exists=True`, so manual removals stay tombstoned.
- Notes: addresses normalized to lowercase; results sorted by timestamp.
