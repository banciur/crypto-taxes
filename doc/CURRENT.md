# Current System Behavior

> **Note:** The legal and tax interpretations described here come from internal research supported by AI tools and may be incomplete. Validate against authoritative guidance before relying on them.

This document is the short first-read summary of the currently implemented domain behavior and cross-cutting system capabilities.

## Purpose

The system is a local-first pipeline for ingesting crypto activity, normalizing it into ledger events, applying manual corrections, and producing a corrected ledger state that can be reviewed and used by downstream wallet, inventory, and tax logic.

## End-to-End Flow

1. Import upstream activity from supported sources into raw `LedgerEvent`s.
2. Persist manual `LedgerCorrection`s that discard, replace, or add opening balances.
3. Rebuild corrected `LedgerEvent`s by applying those corrections to the raw ledger.
4. Rebuild the current wallet projection from corrected events.
5. Rebuild the acquisition/disposal (inventory) projection from the same corrected events.

Current operational output stops after the acquisition/disposal projection is rebuilt. The tax stage exists only as partial downstream work and is not yet the main product output.

The main flow persists a generic latest-run `SystemState` alongside stage outputs. It is `NOT_RUN` until the first run is recorded, `RUNNING` while the active stage is executing, `COMPLETED` after the acquisition/disposal projection succeeds, and `FAILED` with the failed stage and error details (exception type, message, and traceback) when a stage stops the run.

The acquisition/disposal (inventory) stage is modeled around `AcquisitionLot` and `DisposalLink`. Detailed quantity projection, valuation, and FIFO rules for that stage are documented in `doc/LOT_MATCHING.md`.

## Canonical Domain Objects

- `EventOrigin`: stable identity of an upstream raw event, defined by `(location, external_id)`.
- `LedgerEvent`: one imported or corrected operation represented as signed asset movements.
- `LedgerLeg`: one asset delta for one account within a ledger event. `is_fee=True` marks an explicit fee leg.
- `LedgerCorrection`: a manual override that discards raw events, replaces them with a synthetic corrected event, or adds an opening balance.
  - `PriceOverride`: an operator-supplied EUR per-unit rate for one asset of one corrected event, identified by that event's `event_origin` plus the `asset_id`. At most one rate exists per `(event_origin, asset_id)`.
- `AccountRegistry`: the canonical merged account catalog that includes configured real wallets, configured artificial accounts, and built-in exchange accounts.
- `SystemState`: the persisted latest main-flow run status, including stage, start/finish timestamps, and first error details.
- `WalletBalance`: one persisted current balance for an `(account, asset)` pair, rebuilt from corrected events. Rebuild failures surface only through `SystemState`, not through a wallet status object.
- `AcquisitionLot`: an inventory lot created from corrected ledger activity.
- `DisposalLink`: an inventory disposal record that links a disposal quantity to the acquisition lot fragments consumed by FIFO.

## Core Rules

- `EventOrigin` is the stable event identity across imports, corrections, and API/UI flows. Do not build behavior around transient event or leg UUIDs.
- Events may be unbalanced. The system models visible owned activity, not a full double-entry ledger of the outside world.
- Internal timestamps are UTC.
- Quantities and rates use exact decimal semantics. Do not rely on float-style rounding assumptions.
- Within an event, legs are unique by `(account_chain_id, asset_id, is_fee)`.

## Correction Semantics

- `sources != []` and `legs == []`: discard correction
- `sources != []` and `legs != []`: replacement correction
- `sources == []` and `legs != []`: opening-balance correction
- Every claimed source must resolve to exactly one raw event.
- A raw event cannot be claimed by more than one active correction.
- Rebuilding corrected events works by validating source ownership, removing claimed raw events, adding synthetic corrected events for corrections with legs, and then sorting deterministically.
- Deleting a source-backed correction frees that source for manual reuse while preserving auto-suppression so importer automation does not recreate it automatically.

## Price Override Semantics

- An override targets a corrected event by that event's own `event_origin`: a passthrough event's raw origin, or a replacement's or opening balance's synthetic `(INTERNAL, correction.id)` origin. Unlike correction sources, an `INTERNAL` origin is a valid target.
- Every override is re-validated on each rebuild. It is a problem if its `event_origin` matches no corrected event, or if its `asset_id` is absent from that event's legs. Either aborts the `ACQUISITION_DISPOSAL` stage and is recorded as a `FAILED` `SystemState` listing every offending override.
- Matching is by exact origin equality and deliberately does not follow an event across a re-grouping. Folding a priced raw event into a replacement, discarding it, or deleting and recreating its correction (which mints a new id) leaves the override orphaned, so the operator deletes it and re-authors it against the new event.
- The `FAILED` `SystemState` is the only channel through which override problems reach the operator; the API does not re-evaluate them.

## Fee and Valuation Rules

- Swaps and trades net exchange fees into the same-asset leg when possible.
- If a fee is taken in a third asset that is not otherwise part of the event, that fee becomes its own explicit disposal leg.
- Gas and similar execution costs are always separate disposals.
- Reverted on-chain transactions move no value, so they contribute only the gas disposal; their attempted transfers are dropped.
- Explicit fee legs stay explicit downstream through `is_fee=True`.
- `EUR`, configured fiat currencies, and selected stable assets act as valuation anchors. Fiat anchors do not open or consume FIFO lots; selected stable assets still do.
- Asset prices are resolved as cross-rates through a configured numeraire pivot (USD), with stablecoins valued via the fiat currency they are pegged to. A genuinely unavailable market price is a first-class "unpriceable" signal that feeds remainder solving; an operational price-backend failure aborts the run.
- A `PriceOverride` supplies the rate for its asset instead of the price backend, and is then treated as an ordinary known rate: it participates in mid-point rebalancing and remainder solving exactly like a fetched one. This is what makes otherwise-unpriceable events valuable by hand.

## Current Capabilities

- Import raw activity from the supported sources listed below.
- Persist raw ledger events, unified corrections, corrected ledger events, generic system state, current wallet balances, and the acquisition/disposal projection.
- Configure real accounts separately from artificial accounts. Real accounts can feed source importers; artificial accounts are manual ledger accounts exposed for corrections and projections only.
- Review raw events, corrections, and corrected events in the UI.
- Filter those three lanes by a single asset. An event matches when any of its legs holds the asset and is then shown whole; a correction matches on its own legs or on the raw events it claims, so discards stay visible. The acquisition/disposal lane and wallet balances are never filtered.
- Author and remove discard, replacement, and opening-balance corrections through the UI/API flow.
- Author and remove price overrides through the UI/API flow, per asset on a corrected event, and persist them in a durable store (`artifacts/price_overrides.db`).
- Review latest main-flow status, failed stage, and error details (exception type, message, and traceback) in the UI.
- Rebuild the current per-wallet, per-asset balance projection from corrected events.
- Rebuild and persist the acquisition/disposal projection (acquisition lots and disposal links) from corrected events, marking the run `COMPLETED` only after it succeeds.
- Resolve asset prices as numeraire-pivot cross-rates (crypto via CoinMarketCap, fiat via Open Exchange Rates) and cache directional price edges in SQLite (`artifacts/price_cache.db`), negative-caching genuinely-missing prices.

## Current Non-Capabilities

- The main pipeline does not yet run the tax stage; tax computation remains unreachable dead code.
- Tax calculation behavior is incomplete and should not be treated as authoritative current product behavior.
- An orphaned price override (one whose target corrected event no longer exists) fails every rebuild, and the UI offers no way to find or delete it.
- After correction or price-override changes, downstream pipeline outputs still require a manual rerun.

## Supported Sources

- Kraken CSV
- Coinbase Track history
- Stakewise CSV rewards
- Lido CSV rewards
- Moralis on-chain history
