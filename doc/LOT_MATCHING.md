# Lot Matching Model

This document describes the target lot-matching model and rationale for `AcquisitionDisposalProjector`.

## Purpose

The projector sits between corrected ledger events and tax logic.

`LedgerEvent`s tell us what changed in visible owned accounts, but they do not directly answer the questions tax logic needs:

- what quantity of each asset was actually acquired or disposed
- what EUR value should be assigned to that quantity
- which earlier acquisition lots funded each disposal

## Scope

The projector turns chronologically ordered `LedgerEvent`s into:

- `AcquisitionLot`s
- `DisposalLink`s

The projection is split into three steps:
1. **Quantity Projection**: A single event can contain internal transfers between owned accounts, external boundary crossings, routing hops, partial offsets, and explicit fees. The projector first determines the net inventory change per asset.
2. **Assign EUR Values**: The EUR value used by the projector is not always a direct market quote. In this step, the projector uses available event evidence together with pricing data to determine defensible EUR values for the projected assets.
3. **FIFO Matching**: Once projected quantities and EUR values are fixed, the projector matches disposals against earlier acquisition lots and emits the final `AcquisitionLot`s and `DisposalLink`s.

## Core Rules

- Events are already sorted chronologically before projection.
- Open lots are tracked per `asset_id`, not per account.
- `AcquisitionLot.cost_per_unit` and `DisposalLink.proceeds_total` are both EUR-based values.
- `LedgerLeg.quantity` is never zero.
- `LedgerLeg.is_fee=True` means the leg is explicit and must stay explicit downstream.
- Every asset has a valuation tier that says how far its EUR rate can be trusted: `EUR` is exact by definition, other fiat comes from an FX quote, selected stable assets add a peg assumption on top of that quote, and everything else is a market price.
- Anchoring is decided per event, not per asset: every tier stronger than the weakest one present in the event is anchored, so only the weakest tier's rates are proportionally adjusted during balancing.
- Fiat does not open or consume FIFO lots. Selected stable assets still participate in FIFO regardless of how they were valued.
- Each projected acquisition or disposal maps to exactly one source event leg. If one residual quantity comes from multiple current-event legs, it must be split before downstream records are created.
- Fees are not folded into swap or trade consideration. They are separate projected legs because downstream disposals attach to a single source leg.
- Fee valuation is event-coupled. If a fee asset also appears as a non-fee projected asset in the same event, the fee inherits that event's EUR-per-unit rate for the asset.
- `DisposalLink.proceeds_total` is the EUR disposal value assigned to the disposed quantity at the event timestamp. It is a valuation field, not a guarantee of literal cash proceeds.
- Events can be unbalanced because the system sees only owned wallets and visible imported legs.
- Same-event acquisitions must not fund same-event disposals.

## Phase 1: Quantity Projection

For non-fee legs, phase 1 first nets quantities per asset across the whole event. This treats movement of the same asset between owned accounts as internal movement rather than acquisition or disposal. The surviving residual quantity, if any, becomes the projected acquisition or disposal quantity for that asset. A zero residual means the event did not change owned inventory for that asset.

Explicit fee legs are different because their source-leg identity matters downstream. They stay explicit and are projected directly instead of being netted with non-fee movement, even when the fee asset also appears as a non-fee asset in the same event.

Fiat and selected stable assets remain part of the non-fee projection. Their special treatment happens in valuation, not in quantity projection.

If one asset residual survives on multiple same-sign current-event legs, phase 1 must split that residual across those legs. That split is not just an implementation detail. Each projected acquisition or disposal maps to exactly one source event leg, so one projected record cannot represent multiple current-event legs at once.

Examples:

- `Wallet A -1 BTC`, `Wallet B +1 BTC` projects nothing for `BTC`
- `Wallet -1 ETH`, `Wallet +1800 USDC` projects one `ETH` disposal and one `USDC` acquisition
- `A -1 ETH`, `B +0.6 ETH`, `C +0.5 ETH` projects only the `+0.1 ETH` residual acquisition split across B and C legs

## Phase 2: Assign EUR Values

Valuation is event-aware. Pure market pricing is not enough on its own because the event itself can carry stronger valuation evidence. Some assets should anchor the event instead of moving with crypto market noise, and some imported events are unbalanced because the system sees only owned wallets.

For each asset, direct valuation first uses a manual `PriceOverride` targeting that event and asset, then asks the price service at the event timestamp. Some projected assets have neither. In that case, phase 2 may solve one missing non-fee asset as the remainder implied by the other valued non-fee legs in the same event. This only works when the visible non-fee legs contain enough opposing value to infer the missing EUR value.

This is a narrower assumption than the ledger model uses elsewhere. The system generally accepts unbalanced events because unseen external legs may be outside the owned ledger, but phase 2 does not model that uncertainty when it remainder-solves a missing asset value. If economically relevant value is missing from the visible non-fee legs, the inferred EUR value may be wrong even though the event shape is accepted by the broader system.

Phase 2 values the complete event sequence before FIFO matching:

1. Standard-value every event's non-fee groups using manual overrides, price-service rates, same-event remainder solving, and valuation-tier rebalancing.
2. Index the final non-fee rates from events that standard valuation resolved completely.
3. For each unresolved event, find the standard-valued event closest in time that contains one of its unresolved assets. Past and future events are both eligible. Equal-distance candidates are selected deterministically by stable event origin, then asset id.
4. Borrow that asset's final rate transiently and retry the target event's normal non-fee valuation from the beginning. Repeat until the event resolves or no eligible anchor remains.
5. Resolve fees after every event has final non-fee rates.

Only standard-valued events enter the anchor index. An event that needs an adjacent rate cannot anchor another event, so resolution never recurses or forms derived-rate chains. Borrowed rates exist only during the current projection and are not persisted as `PriceOverride`s.

A two-sided event may finish after borrowing fewer rates than it originally lacked because the final missing rate can be remainder-solved from the event itself. A one-sided event has no opposing value, so every unavailable non-fee rate must come from an adjacent anchor.

Valuation-tier rebalancing is what makes a `EUR`/`DAI` trade work. Both assets are reference-priced, but they are not equally trustworthy: the EUR leg *is* the EUR value, while `DAI`'s rate is a peg assumption on top of a daily FX quote. The exchange spread makes the two disagree by a fraction of a percent. Anchoring `EUR` and letting `DAI` absorb the difference values the acquired `DAI` at what was actually paid for it. The same ordering keeps a stable anchored against a market asset, so an `ETH`/`USDC` trade still takes its valuation from the `USDC` leg.

Only the weakest tier moves, not every tier below the strongest. In a `EUR -> ETH + USDC` event the discrepancy is absorbed entirely by `ETH`; `USDC` keeps its own rate rather than being dragged around by `ETH`'s pricing error.

An event whose assets all share one tier has nothing stronger to anchor against, so all of its groups are adjustable. Two market assets rebalance against each other, and so do two stables.

When both sides of the event contain adjustable assets, the adjustment is symmetric and moves both sides toward a midpoint. When only one side contains adjustable assets, that side absorbs the adjustment.

Fees stay structurally separate from non-fee legs and do not participate in the non-fee balancing equation. After non-fee rates are resolved, a fee first tries to inherit the same-event EUR-per-unit rate for the same asset. If that is not available, it falls back to direct pricing.

The phase should produce defensible EUR-per-unit rates that later phases can use directly.

## Failure Boundaries

Projection must fail when automatic valuation cannot produce a defensible result.

Important failure boundaries:

- one or more non-fee assets remain unavailable and none has an eligible standard-valued adjacent anchor
- a reference-priced asset (fiat or a selected stable) cannot be priced directly in EUR, which means the price data is broken rather than the asset being genuinely unpriceable
- a fee asset appears only in fee legs and cannot be priced in EUR
- remainder solving would require negative value
- the event totals disagree and the adjustable assets are valued at zero, leaving nothing that can absorb the difference
- the price backend fails operationally

## Phase 3: FIFO Matching

FIFO matches each projected non-fiat disposal against older open acquisition lots of the same asset. Fiat does not open or consume FIFO lots. Disposals are processed before acquisitions so that a same-event acquisition residual cannot fund a same-event disposal residual, and a single projected disposal leg may still produce multiple `DisposalLink`s, one for each historical lot fragment consumed by FIFO.

## Consequences of the Model

- Internal transfers do not create fresh tax lots.
- Moving an asset between owned accounts does not reset FIFO because lots are tracked per asset, not per account.
- Fees remain explicit and separately deductible / taxable because they keep their own source-leg identity through `is_fee=True`.
- Fiat and selected stable consideration anchor event valuation against weaker-tier assets instead of being proportionally adjusted alongside them. Fiat does this without creating or consuming FIFO lots, while selected stable assets remain lot-tracked.
- A trade between two reference-priced assets is valued by the trade itself rather than by two independently quoted rates that will never agree exactly.
- Assets without direct prices can borrow transient rates from nearby independently valued events without creating persisted corrections or derived-rate chains.
- Current-event valuation is determined before inventory history is consulted.

## Operator-Supplied Valuation Corrections

Some events remain impossible to value automatically because no standard-valued adjacent anchor exists. A manual `PriceOverride` supplies a EUR-per-unit rate for one asset of one corrected event, identified by the event's stable `EventOrigin` and the `asset_id`.

Manual overrides take precedence over the price service, participate in same-event remainder solving and rebalancing, and make a fully standard-valued event eligible as an adjacent anchor. Their targeting and validation semantics are documented in `doc/CURRENT.md`.
