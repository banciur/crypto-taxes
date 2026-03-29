# AI Dev Guide — Current State and Capabilities

> **Note:** The legal/tax interpretations described here stem from internal research supported by AI tools and may not be exhaustive. Validate against authoritative guidance before relying on them.

This document captures the currently implemented domain for modeling crypto ledger activity for tax purposes. It reflects the simplified approach we are taking now to keep iteration fast.

---

## Scope

- Represent basic events with legs, without enforcing double-entry balancing.
- Minimal inventory structures for lots and disposals.
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
  - `acquired_leg_id: UUID`
  - `cost_per_unit: Decimal`

- DisposalLink
  - `id: UUID`
  - `disposal_leg_id: UUID`
  - `lot_id: UUID`
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
  - `price_per_token: Decimal | None`
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

## Behavioral Notes

- Inventory processing is automated: the `InventoryEngine` creates `AcquisitionLot`s and `DisposalLink`s from ordered events using FIFO matching.
- EUR legs on an event take precedence for valuing acquisitions/disposals. Only when no unambiguous EUR leg exists do we fall back to the injected `PriceProvider` for EUR pricing.
- Unbalanced events are allowed.
- Precision: use `Decimal` for all quantities/rates. No floats.
- Time: store all timestamps in UTC; perform any timezone conversion at data ingress (when time enters the system) so internal models always carry UTC `timestamp` values.
- Inventory processing assumes events are already sorted chronologically; ingestion layers must enforce ordering before invoking the engine. Open lots are tracked per asset (not per account) and matched FIFO.
- Internal account-to-account transfers are identified structurally (same-asset non-fee legs netting to zero inside one event) and do not create lots or disposal links.
- Each event captures `event_origin` (where the transaction happened and its upstream id) and `ingestion` (which importer produced it).
- `LedgerEvent.note` is optional display metadata. Moralis populates it from a trimmed upstream `method_label` when that label is available.
- Raw `ledger_events` are stored with a DB-level uniqueness constraint on `EventOrigin` (`origin_location` + `origin_external_id`).
- `AccountRegistry` is the canonical account catalog exposed to the UI. It merges configured wallet accounts from `accounts.json` with built-in system exchange accounts (currently Coinbase and Kraken). System accounts do not participate in address-based ownership resolution and use location-derived IDs such as `COINBASE:coinbase`.
- Ingestion corrections are applied in this order: validate unified source ownership, remove claimed raw events, emit synthetic corrected events for corrections with legs, then sort once before persisting corrected events by `timestamp`, `event_origin.location`, and `event_origin.external_id`.
- Corrections are persisted in the corrections DB as active header rows plus source rows plus leg rows, with a separate source-level auto-suppression table. Deleting a source-backed correction hard-deletes the correction and frees the source for explicit manual reuse while preserving auto-suppression for future importer runs; deleting a source-less opening-balance correction is a plain hard delete.
- Validation is strict: every claimed source must match exactly one raw event, and a raw event cannot be consumed by more than one active correction source.
- Moralis possible-spam auto-generation creates discard corrections and respects active source claims plus source-level auto-suppressions so manually removed corrections are not recreated automatically.
- The UI can author discard, replacement, and opening-balance corrections through the unified corrections API.
- Wallet tracking is a separate projection over corrected events. It processes events in canonical deterministic order, tracks all assets including fiat, and validates event deltas atomically and store outcome in database.

---

## Fees

- Swaps and trades (custodial or on-chain) net their exchange fees into whichever leg uses the same asset: if the fee reduces the asset being spent, we decrease that outgoing quantity; if it comes out of what you acquired, we shrink the inbound leg. Only when the fee is taken in an asset that is not otherwise part of the event do we emit a separate disposal leg, allowing FIFO to consume that third asset and value it like any other disposal. Stablecoins follow the same rule as any crypto.
- Execution costs such as gas are independent on-chain spends and always produce their own disposal legs, even if they happen in the same transaction as the swap. Paying ETH for gas when swapping WETH/WBTC still records an ETH disposal.
- Deposits and withdrawals are modeled as single Kraken-side legs. Counterparty legs are not emitted.
- Explicit fee legs set `is_fee=True` on the leg. Downstream views should use that to exclude fees from income while still valuing them for tax deductibility.

---

## Current Capabilities

- Model simple acquisitions/disposals with per-leg accounts and optional fee legs.
- Automatically create lots for acquisitions and link disposals via `InventoryEngine.process` (FIFO only; other lot policies are future work).
- Resolve EUR valuations through the injected `PriceProvider`; pricing data may be cached or persisted by the backing service.
- Wallet tracking rebuilds a current-state per-wallet/per-asset projection from corrected events and persists it in SQLite.
- `GET /wallet-tracking` exposes the current wallet-tracking snapshot with `NOT_RUN`/`COMPLETED`/`FAILED` semantics.
- Tax calculations currently focus on disposal links.
- CLI run persists ledger events plus corrected ledger events to SQLite, rebuilds the current wallet-tracking snapshot, and then stops before later inventory/tax stages in the current implementation.

### User Interface

- The UI supports reviewing raw events, unified persisted corrections, and corrected events.
- The UI can author and remove unified corrections: discard, replacement, and opening-balance.
- After correction mutations, the UI refreshes the server-rendered lane data immediately.
- Corrected pipeline outputs still require a manual rerun after correction mutations.
- Wallet-tracking backend delivery exists through `GET /wallet-tracking`, but the UI does not render that state yet.

---

## Supported Sources

- Kraken ledger CSV
- Coinbase Track account history
- On-chain transactions via Moralis
