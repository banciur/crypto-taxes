# Moralis importer

- Purpose: fetch on-chain transactions via `MoralisService.get_transactions` and translate them into `LedgerEvent`s.
- Scope: ERC20 and native transfers; NFT transfers are ignored.
- Flow:
  - Fetch transactions through `MoralisService` which caches them using `MoralisCacheRepository`.
  - Build legs from `native_transfers` and `erc20_transfers` only for owned accounts, unknown counterparties are ignored.
  - Parse ERC20 quantities from raw integer `value` plus `token_decimals` when decimals metadata is present.
  - If Moralis omits ERC20 decimals metadata and `value_formatted` is unusable (for example `NaN`), fall back to raw integer `value`.
  - Collapse legs by (`asset_id`, `account_chain_id`, `is_fee`) inside each transaction so same-token round-trips net to one leg.
  - Filter out from native transfers ones that Moralis sends as part of the fee (probably a bug).
  - Add a fee leg from `transaction_fee` when tx sender resolves to an owned account (`ETH`, `is_fee=True`).
  - Set `LedgerEvent.note` from Moralis `method_label` after trimming whitespace; leave it empty when Moralis does not provide a method label.
  - Event emission: emit an event when there is at least one owned leg; otherwise skip tx.
  - Automatic discard persistence: when a transaction emits an event and Moralis sets `possible_spam=true`, the importer writes a source-backed `LedgerCorrection` with no legs, unless that source already has an active correction or a source-level auto-suppression.
- Notes: addresses normalized to lowercase; results sorted by timestamp.
