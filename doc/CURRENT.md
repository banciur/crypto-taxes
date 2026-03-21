# AI Dev Guide — Current State and Capabilities

> **Note:** The legal/tax interpretations described here stem from internal research supported by AI tools and may not be exhaustive. Validate against authoritative guidance before relying on them.

This document captures the currently implemented domain for modeling crypto ledger activity for tax purposes. It reflects the simplified approach we are taking now to keep iteration fast.

---

## Scope

- Represent basic events with legs, without enforcing double-entry balancing.
- Minimal inventory structures for lots and disposals.
- Unified price snapshots for crypto and fiat pairs.
- First take on tax calculation

---

## Core Models

- LedgerEvent
  - `id: UUID`
  - `timestamp: datetime`
  - `event_origin: EventOrigin` (upstream location + external transaction id)
  - `ingestion: str` (import pipeline label, e.g., `kraken_ledger_csv`, `ledger_correction`)
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
- Internal account-to-account transfers are identified structurally (same-asset non-fee legs netting to zero inside one event) and only update balances. They do not create lots or disposal links.
- Per-account balances are tracked for all non-EUR legs; any debit that would push an account negative raises an error. Fix missing history by adding prior movements into the source account or authoring an opening-balance correction.
- Each event captures `event_origin` (where the transaction happened and its upstream id) and `ingestion` (which importer produced it).
- Raw `ledger_events` are stored with a DB-level uniqueness constraint on `EventOrigin` (`origin_location` + `origin_external_id`).
- `AccountRegistry` is the canonical account catalog exposed to the UI. It merges configured wallet accounts from `accounts.json` with built-in system exchange accounts (currently Coinbase and Kraken). System accounts do not participate in address-based ownership resolution and use location-derived IDs such as `COINBASE:coinbase`.
- Ingestion corrections are applied in this order: validate unified source ownership, remove claimed raw events, emit synthetic corrected events for corrections with legs, then sort once before persisting corrected events.
- Corrections are persisted in the corrections DB as header rows plus source rows plus leg rows. Source-backed deletions become tombstones by soft-deleting the correction row while retaining its source rows for suppression checks; source-less opening-balance deletions are hard deletes.
- Validation is strict: every claimed source must match exactly one raw event, and a raw event cannot be consumed by more than one active correction source.
- Moralis possible-spam auto-generation creates discard corrections and respects deleted-source tombstones so manually removed auto-generated corrections are not recreated.
- The UI can author discard, replacement, and opening-balance corrections through the unified corrections API.
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
- CLI inventory summary aggregates quantities and EUR values per asset across owned accounts.
- Tax calculations currently focus on disposal links.
- CLI run persists ledger events plus corrected ledger events to SQLite, and the backend correction pipeline supports unified `LedgerCorrection` records only.
- The UI renders raw, corrections, and corrected lanes. Raw-backed event cards in the raw/corrected lanes support selection keyed by `event_origin` for discard and replacement actions, the corrections lane displays unified persisted corrections, and the corrected lane shows corrected ledger events including synthetic `ledger_correction` events. After correction mutations the UI refreshes the server-rendered page so the corrections lane updates immediately; the corrected lane still requires a pipeline rerun.

---

## Supported Sources

- Kraken ledger CSV
- Coinbase Track account history
- On-chain transactions via Moralis
