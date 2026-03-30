# Coinbase importer

- Purpose: translate cached Coinbase Track account history into domain `LedgerEvent`s.
- Source of truth: the Coinbase tables in `artifacts/transactions_cache.db`.
- Scope: Coinbase Track wallet activity only; Coinbase is modeled as one consolidated `account_chain_id="COINBASE:coinbase"` rather than per-asset wallets.

## Flow

1. `CoinbaseImporter.load_events()` calls `CoinbaseService.get_history(sync_mode)`.
2. `CoinbaseService` either reuses the cached Coinbase history or refreshes the full Coinbase source, depending on `SyncMode` and the whole-source last sync timestamp.
3. `CoinbaseImporter` groups account-centric rows into logical events and emits `LedgerEvent`s with `location=COINBASE`.
4. Events are sorted by timestamp before returning.

## Grouping rules

- `buy`: grouped by `buy.id`. Two-row wallet-funded buys keep the reported rows. Single-row card-funded buys synthesize a negative quote-currency leg from `buy.total`.
- `sell`: grouped by `sell.id`. Two-row sells keep the reported rows. Single-row sells would synthesize the positive quote leg from `sell.total`.
- `trade`: grouped by `trade.id`. The negative row is the spend leg and the positive row is the acquire leg.
- `wrap_asset`: paired by nearest opposite-sign row within two seconds and emitted as one swap event with a synthetic origin id derived from the member row ids.

## Skip / defer rules

- `staking_transfer`: paired by normalized asset + absolute quantity within two seconds and dropped as an internal wallet move.
- `retail_eth2_deprecation`: dropped as an internal `ETH2 -> ETH` migration after alias normalization.
- `fiat_deposit` + `exchange_deposit`: same-account, same-currency, same-amount pairs within ten seconds are dropped as pass-through transfers into Coinbase Exchange.
- `pro_deposit` / `pro_withdrawal`: explicitly deferred for now because they are cross-product boundary rows and do not fit the consolidated Coinbase model without more source coverage.

## Normalization notes

- Asset aliasing currently normalizes `ETH2 -> ETH`.
- `send` rows are emitted one-for-one; outgoing sends with non-zero `network.transaction_fee` split Coinbase's total-debited `amount` into a net transfer leg plus a separate fee leg.
- Reward-like inflows (`staking_reward`, `earn_payout`, `interest`, `tx`) emit as single positive legs.
- Unknown future Coinbase types should raise until an explicit handler is added.
