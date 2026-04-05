# AI Dev Guide — Current State and Capabilities

> **Note:** The legal/tax interpretations described here stem from internal research supported by AI tools and may not be exhaustive. Validate against authoritative guidance before relying on them.

This document captures the currently implemented domain for modeling crypto ledger activity for tax purposes. It reflects the simplified approach we are taking now to keep iteration fast.

---

## Scope

- Represent basic events with legs, without enforcing double-entry balancing.
- Minimal acquisition/disposal projection structures.
- Current-state wallet tracking from corrected ledger events.
- Unified price snapshots for crypto and fiat pairs.
- First take on tax calculation

---

## Core Models

- LedgerEvent
  - `id: UUID`
  - `timestamp: datetime`
  - `event_origin: EventOrigin` (upstream location + external transaction id)
  - `ingestion: str` (import pipeline label, e.g., `kraken_ledger_csv`, `ledger_correction`)
  - `note: str | None`
  - `legs: list[LedgerLeg]`

- LedgerLeg
  - `id: UUID`
  - `asset_id: str`
  - `quantity: Decimal`
  - `account_chain_id: str`
  - `is_fee: bool`

- AcquisitionLot
  - `id: UUID`
  - `event_origin: EventOrigin`
  - `account_chain_id: str`
  - `asset_id: str`
  - `is_fee: bool`
  - `timestamp: datetime`
  - `quantity_acquired: Decimal`
  - `cost_per_unit: Decimal`

- DisposalLink
  - `id: UUID`
  - `lot_id: UUID`
  - `event_origin: EventOrigin`
  - `account_chain_id: str`
  - `asset_id: str`
  - `is_fee: bool`
  - `timestamp: datetime`
  - `quantity_used: Decimal`
  - `proceeds_total: Decimal`

- TaxEvent
  - `source_id: UUID` (a `DisposalLink` for disposals, an `AcquisitionLot` for rewards)
  - `kind: TaxEventKind` (`DISPOSAL`, `REWARD`)
  - `taxable_gain: Decimal`

- WalletTrackingState
  - `status: WalletTrackingStatus` (`NOT_RUN`, `COMPLETED`, `FAILED`)
  - `failed_event: EventOrigin | None`
  - `issues: list[WalletTrackingIssue]`
  - `balances: list[WalletBalance]`

- WalletBalance
  - `account_chain_id: str`
  - `asset_id: str`
  - `balance: Decimal`

- WalletTrackingIssue
  - `event: EventOrigin`
  - `account_chain_id: str`
  - `asset_id: str`
  - `attempted_delta: Decimal`
  - `available_balance: Decimal`
  - `missing_balance: Decimal`

- LedgerCorrection
  - `id: UUID`
  - `timestamp: datetime`
  - `sources: list[EventOrigin]`
  - `legs: list[LedgerLeg]`
  - `note: str | None`
  - Shape semantics:
    - `sources != []` and `legs == []` => discard correction
    - `sources != []` and `legs != []` => replacement correction
    - `sources == []` and `legs != []` => opening-balance correction

- EventOrigin
  - `location: EventLocation` (`ETHEREUM`, `ARBITRUM`, `KRAKEN`, `COINBASE`...)
  - `external_id: str`

- PriceProvider (protocol)
  - `rate(base_id: str, quote_id: str, timestamp: datetime) -> Decimal`
  - Current runtime wiring: `PriceService` composes a CoinDesk spot source for any pair touching crypto assets and an Open Exchange Rates source for fiat↔fiat pairs (EUR, PLN, USD), persisting snapshots via the JSONL store so downstream components can stay stateless.

---

## Current Capabilities

- Represent imported and corrected operations as `LedgerEvent`s composed of signed `LedgerLeg`s that record the participating account and asset quantity.
- Project those events into acquisitions/disposals with per-leg accounts and optional fee legs. Detailed algorithm rules live in `doc/LOT_MATCHING.md`.
- Tax calculations currently focus on disposal links (currently doesn't work as being worked on)
- Resolve EUR valuations through the injected `PriceProvider`; pricing data may be cached or persisted by the backing service.
- Wallet tracking rebuilds a current-state per-wallet/per-asset projection from corrected events and persists it in SQLite. It's exposed through `GET /wallet-projection`.
- CLI run persists ledger events plus corrected ledger events to SQLite, rebuilds the current wallet projection snapshot, and then stops before later inventory/tax stages in the current implementation. The raw-event import step currently combines Kraken, Stakewise, and Lido CSVs, Coinbase Track history, Moralis on-chain history.

---

## Fees

- Swaps and trades (custodial or on-chain) net their exchange fees into whichever leg uses the same asset: if the fee reduces the asset being spent, we decrease that outgoing quantity; if it comes out of what you acquired, we shrink the inbound leg. Only when the fee is taken in an asset that is not otherwise part of the event do we emit a separate disposal leg, allowing FIFO to consume that third asset and value it like any other disposal. Stablecoins follow the same rule as any crypto.
- Execution costs such as gas are independent on-chain spends and always produce their own disposal legs, even if they happen in the same transaction as the swap. Paying ETH for gas when swapping WETH/WBTC still records an ETH disposal.
- Explicit fee legs set `is_fee=True` on the leg. Downstream views should use that to exclude fees from income while still valuing them for tax deductibility.

---

### User Interface

- The UI supports reviewing raw events, unified persisted corrections, and corrected events.
- The UI can author and remove unified corrections: discard, replacement, and opening-balance.
- After correction mutations, the UI refreshes the server-rendered lane data immediately.
- Corrected pipeline outputs still require a manual rerun after correction mutations.
- Wallet projection backend delivery exists through `GET /wallet-projection`, and the UI renders that state in the page header section.

---

## Behavioral Notes

- Unbalanced events are allowed.
- Precision: use `Decimal` for all quantities/rates. No floats.
- Time: store all timestamps in UTC; perform any timezone conversion at data ingress (when time enters the system) so internal models always carry UTC `timestamp` values.
- Each event captures `event_origin` (where the transaction happened and its upstream id) and `ingestion` (which importer produced it).
- `LedgerEvent.note` is optional display metadata. Moralis populates it from a trimmed upstream `method_label` when that label is available.
- Raw `ledger_events` are stored with a DB-level uniqueness constraint on `EventOrigin` (`origin_location` + `origin_external_id`).
- `AccountRegistry` is the canonical account catalog exposed to the UI. It merges configured wallet accounts from `accounts.json` with built-in system exchange accounts (currently Coinbase and Kraken). System accounts do not participate in address-based ownership resolution and use location-derived IDs such as `COINBASE:coinbase`.
- Stakewise CSV rewards are imported onto the Ethereum wallet configured via `STAKING_REWARDS_WALLET_ADDRESS`
- Lido CSV rewards are imported from `artifacts/lido.csv` onto the same Ethereum wallet configured via `STAKING_REWARDS_WALLET_ADDRESS`
- Ingestion corrections are applied in this order: validate unified source ownership, remove claimed raw events, emit synthetic corrected events for corrections with legs, then sort once before persisting corrected events by `timestamp`, `event_origin.location`, and `event_origin.external_id`.
- Corrections are persisted in the corrections DB as active header rows plus source rows plus leg rows, with a separate source-level auto-suppression table. Deleting a source-backed correction hard-deletes the correction and frees the source for explicit manual reuse while preserving auto-suppression for future importer runs; deleting a source-less opening-balance correction is a plain hard deletion.
- Validation is strict: every claimed source must match exactly one raw event, and a raw event cannot be consumed by more than one active correction source.
- Moralis possible-spam auto-generation creates discard corrections and respects active source claims plus source-level auto-suppressions so manually removed corrections are not recreated automatically.
- The UI can author discard, replacement, and opening-balance corrections through the unified corrections API.
- Wallet tracking is a separate projection over corrected events. It processes events in canonical deterministic order, tracks all assets including fiat, and validates event deltas atomically and store outcome in database.

---

## Supported Sources

- Kraken - through CSV
- Coinbase - through API 
- Stakewise - through CSV 
- Lido - through CSV
- On-chain transactions via Moralis
