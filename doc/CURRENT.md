# AI Dev Guide — Current State and Capabilities

This document captures the currently implemented domain for modeling crypto ledger activity. It reflects the simplified approach we are taking now to keep iteration fast. A separate document describes the target (future) architecture.

---

## Scope (Now)

- Represent basic events with legs, without enforcing double-entry balancing.
- Minimal inventory structures for lots and disposals.
- Unified price snapshots for crypto and fiat pairs.

---

## Core Models

- LedgerEvent
  - `id: UUID`
  - `timestamp: datetime`
  - `event_type: EventType` (currently only `TRADE` is implemented; other event types will come shortly)
  - `legs: list[LedgerLeg]`

- LedgerLeg
  - `id: UUID`
  - `asset_id: str`
  - `quantity: Decimal`
  - `wallet_id: str`
  - `is_fee: bool`

- AcquisitionLot
  - `id: UUID`
  - `acquired_event_id: UUID`
  - `acquired_leg_id: UUID`
  - `cost_eur_per_unit: Decimal`

- DisposalLink
  - `id: UUID`
  - `disposal_leg_id: UUID`
  - `lot_id: UUID`
  - `quantity_used: Decimal`
  - `proceeds_total_eur: Decimal`

- PriceProvider (protocol)
  - `rate(base_id: str, quote_id: str, timestamp: datetime) -> Decimal`
  - Current runtime wiring: `PriceService` composes a CoinDesk spot source for any pair touching crypto assets and an Open Exchange Rates source for fiat↔fiat pairs (EUR, PLN, USD), persisting snapshots via the JSONL store so downstream components can stay stateless.

---

## Behavioral Notes

- Inventory processing is automated: the `InventoryEngine` creates `AcquisitionLot`s and `DisposalLink`s from ordered events using FIFO matching. Alternate policies (`HIFO`, `SPEC_ID`) are planned but not yet implemented.
- Unbalanced events are allowed.
- Fee legs: modeled as additional legs with `is_fee=True`.
- Precision: use `Decimal` for all quantities/rates. No floats.
- Time: store all timestamps in UTC; perform any timezone conversion at data ingress (when time enters the system) so internal models always carry UTC `timestamp` values.
- Inventory processing assumes events are already sorted chronologically; ingestion layers must enforce ordering before invoking the engine.

---

## Current Capabilities

- Model simple trades and transfers with per-leg wallets and optional fee legs.
- Automatically create lots for acquisitions and link disposals via `InventoryEngine.process` (FIFO only; other lot policies are future work).
- Resolve EUR valuations through the injected `PriceProvider`; pricing data may be cached or persisted by the backing service.
