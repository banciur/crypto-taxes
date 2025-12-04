# AI Dev Guide — Current State and Capabilities

> **Note:** The legal/tax interpretations described here stem from internal research supported by AI tools and may not be exhaustive. Validate against authoritative guidance before relying on them.

This document captures the currently implemented domain for modeling crypto ledger activity fox tax purposes. It reflects the simplified approach we are taking now to keep iteration fast.

---

## Scope (Now)

- Represent basic events with legs, without enforcing double-entry balancing.
- Minimal inventory structures for lots and disposals.
- Unified price snapshots for crypto and fiat pairs.
- First take on tax calculation

---

## Core Models

- LedgerEvent
  - `id: UUID`
  - `timestamp: datetime`
  - `origin: EventOrigin` (upstream location + external transaction id)
  - `ingestion: str` (import pipeline label, e.g., `kraken_ledger_csv`, `seed_csv`)
  - `event_type: EventType` (currently includes `TRADE`, `DEPOSIT`, `WITHDRAWAL`, `TRANSFER`, `REWARD`)
  - `legs: list[LedgerLeg]`

- LedgerLeg
  - `id: UUID`
  - `asset_id: str`
  - `quantity: Decimal`
  - `wallet_id: str`
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
- Inventory processing assumes events are already sorted chronologically; ingestion layers must enforce ordering before invoking the engine. Open lots are tracked per asset (not per wallet) and matched FIFO.
- Transfers (`EventType.TRANSFER`) only update wallet balances so overspending is caught; they do not create or move lots.
- Per-wallet balances are tracked for all non-EUR legs; any debit that would push a wallet negative raises an error. Fix missing history by seeding lots or adding prior transfers into the source wallet before processing.
- Synthetic seed lots can be injected ahead of importer output to satisfy transfers from `outside` when historical sources are missing. The CLI accepts `--seed-csv` (default `data/seed_lots.csv`) with rows `asset_id,wallet_id,quantity[,timestamp,cost_total_eur]`; these are modeled as tiny-cost trades (default cost 0.0001 EUR, timestamp defaults to 2000-01-01Z) so FIFO can move them like any other lot. Missing inventory will surface as an error during processing and should be resolved by updating the seed CSV manually.
- Each event captures `origin` (where the transaction happened and its upstream id) and `ingestion` (which importer produced it).

---

## Fees

- Swaps and trades (custodial or on-chain) net their exchange fees into whichever leg uses the same asset: if the fee reduces the asset being spent, we decrease that outgoing quantity; if it comes out of what you acquired, we shrink the inbound leg. Only when the fee is taken in an asset that is not otherwise part of the event do we emit a separate disposal leg, allowing FIFO to consume that third asset and value it like any other disposal. Stablecoins follow the same rule as any crypto.
- Execution costs such as gas are independent on-chain spends and always produce their own disposal legs, even if they happen in the same transaction as the swap. Paying ETH for gas when swapping WETH/WBTC still records an ETH disposal.
- Deposits and withdrawals route funds between the `outside` wallet and the exchange wallet without separate fee legs. Deposits decrease the `outside` wallet by the deposited amount while the `kraken` leg reflects the fee-reduced credit; withdrawals increase the `outside` wallet by what the recipient receives while the `kraken` leg spends the amount plus fees.
- Explicit fee legs set `is_fee=True` on the leg. Downstream views should use that to exclude fees from income while still valuing them for tax deductibility.

---

## Current Capabilities

- Model simple trades and transfers with per-leg wallets and optional fee legs.
- Automatically create lots for acquisitions and link disposals via `InventoryEngine.process` (FIFO only; other lot policies are future work).
- Resolve EUR valuations through the injected `PriceProvider`; pricing data may be cached or persisted by the backing service.
- CLI inventory summary aggregates quantities and EUR values per asset across owned wallets (no tax-free window split).
- Tax events cover disposals inside the 1-year window and `REWARD` acquisitions taxed at receipt using their EUR value.
- CLI run persists ledger events, acquisition lots, disposal links, and tax events to SQLite for inspection and reuse.
