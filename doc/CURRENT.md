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
  - `event_origin: EventOrigin` (upstream location + external transaction id)
  - `ingestion: str` (import pipeline label, e.g., `kraken_ledger_csv`, `seed_csv`)
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
- Per-account balances are tracked for all non-EUR legs; any debit that would push an account negative raises an error. Fix missing history by seeding lots or adding prior movements into the source account before processing.
- Synthetic seed lots can be injected ahead of importer output using `--seed-csv` (default `artifacts/seed_lots.csv`) with rows `asset_id,account_id,quantity[,timestamp,price_per_token]`; `timestamp` defaults to `2000-01-01T00:00:00Z` and `price_per_token` defaults to `0`.
- Each event captures `event_origin` (where the transaction happened and its upstream id) and `ingestion` (which importer produced it).
- Raw `ledger_events` are stored with a DB-level uniqueness constraint on `EventOrigin` (`origin_location` + `origin_external_id`).
- Spam corrections are persisted in a separate DB so they survive resets of the main analytics DB. That persistence layer keeps soft-delete tombstones and provenance metadata internally so automatic imports can avoid recreating markers that were removed manually.

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
- CLI run persists ledger events, acquisition lots, disposal links, and tax events to SQLite for inspection and reuse.
- The UI now renders raw, corrections, and corrected lanes. The raw lane supports per-event spam selection, the corrections lane displays seed events with spam markers, and the corrected lane shows only corrected ledger events.

---

## External data: on-chain transactions (via Moralis, cached)

- Purpose: fetch on-chain wallet transaction history via Moralis with the caching feature.
- Entry point: `MoralisService.get_transactions(mode)` in `data/src/clients/moralis.py`; loads accounts from `artifacts/accounts.json`, ensures chains are synced, then returns all cached transactions ordered at the DB level.
- Accounts config entries include `name`, `chains`, and `skip_sync`; `skip_sync=true` excludes that account from future fetches while retaining it in tracked account metadata.
- Sync policy: supports `FRESH` (always refresh each configured account/chain pair) and `BUDGET` (skip account/chain pairs already synced through yesterday). New account/chain pairs fetch full history; previously synced pairs use a 1-day overlap from their own sync cursor.
- Implementation and schema details live in `data/src/clients/AGENTS.md`.
- Importer output currently covers ERC20 and native transfers plus fees for owned accounts. NFT transfers are ignored.
- When the Moralis payload marks a transaction with `possible_spam=true` and the importer emits a `LedgerEvent`, the importer also persists an `AUTO_MORALIS` spam correction in the corrections DB. Those automatic writes use `skip_if_exists=True`, so a manually removed spam marker is not recreated by later imports.
