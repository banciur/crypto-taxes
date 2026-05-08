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
5. Feed corrected events into downstream inventory and tax stages.

Current operational output stops after corrected-ledger persistence and wallet projection rebuild. Inventory and tax stages exist only as partial downstream work and are not yet the main product output.

The downstream inventory stage is modeled around `AcquisitionLot` and `DisposalLink`. Detailed quantity projection, valuation, and FIFO rules for that stage are documented in `doc/LOT_MATCHING.md`.

## Canonical Domain Objects

- `EventOrigin`: stable identity of an upstream raw event, defined by `(location, external_id)`.
- `LedgerEvent`: one imported or corrected operation represented as signed asset movements.
- `LedgerLeg`: one asset delta for one account within a ledger event. `is_fee=True` marks an explicit fee leg.
- `LedgerCorrection`: a manual override that discards raw events, replaces them with a synthetic corrected event, or adds an opening balance.
- `AccountRegistry`: the canonical merged account catalog that includes both configured wallets and built-in exchange accounts.
- `WalletTrackingState`: the persisted result of rebuilding current balances from corrected events, including status, balances, and blocking issues.
- `AcquisitionLot`: a downstream inventory lot created from corrected ledger activity.
- `DisposalLink`: a downstream inventory disposal record that links a disposal quantity to the acquisition lot fragments consumed by FIFO.

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

## Fee and Valuation Rules

- Swaps and trades net exchange fees into the same-asset leg when possible.
- If a fee is taken in a third asset that is not otherwise part of the event, that fee becomes its own explicit disposal leg.
- Gas and similar execution costs are always separate disposals.
- Explicit fee legs stay explicit downstream through `is_fee=True`.
- `EUR`, configured fiat currencies, and selected stable assets act as valuation anchors. Fiat anchors do not open or consume FIFO lots; selected stable assets still do.

## Current Capabilities

- Import raw activity from the supported sources listed below.
- Persist raw ledger events, unified corrections, corrected ledger events, and wallet projection state.
- Review raw events, corrections, and corrected events in the UI.
- Author and remove discard, replacement, and opening-balance corrections through the UI/API flow.
- Rebuild the current per-wallet, per-asset balance projection from corrected events.
- Persist price snapshots that downstream valuation logic can use.

## Current Non-Capabilities

- The main pipeline does not yet treat inventory and tax stages as the primary operational output.
- Tax calculation behavior is incomplete and should not be treated as authoritative current product behavior.
- Operator-supplied valuation overrides for hard-to-price events are not implemented.
- After correction changes, downstream pipeline outputs still require a manual rerun.

## Supported Sources

- Kraken CSV
- Coinbase Track history
- Stakewise CSV rewards
- Lido CSV rewards
- Moralis on-chain history
