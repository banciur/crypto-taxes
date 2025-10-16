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
  - `event_type: EventType`
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

- PriceSnapshot (unified)
  - `timestamp: datetime`
  - `base_id: str`,
  - `quote_id: str`
  - `rate: Decimal`
  - `source: str`,

---

## Behavioral Notes

- Unbalanced events are allowed.
- Fee legs: modeled as additional legs with `is_fee=True`.
- Precision: use `Decimal` for all quantities/rates. No floats.
 - Time: store all timestamps in UTC; perform any timezone conversion at data ingress (when time enters the system) so internal models always carry UTC `timestamp` values.

---

## Current Capabilities

- Model simple trades and transfers with per-leg wallets and optional fee legs.
- Create lots for acquisitions and link disposals manually via `DisposalLink`.
- Record price snapshots uniformly for later valuation.
