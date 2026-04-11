# Lot Matching Model

This document describes the target lot-matching model and rationale for `AcquisitionDisposalProjector`.

Implementation work needed to reach this target is tracked in `data/PLAN.md`.

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
- Non-fee `EUR` is a valuation anchor. It already carries EUR value in the event and is not proportionally adjusted during balancing.
- Other fiat currencies and selected stable assets are also treated as valuation anchors. They may need direct EUR pricing first, but once valued, they are not proportionally adjusted during balancing.
- Fiat valuation anchors do not open or consume FIFO lots. Selected stable anchors still participate in FIFO.
- Fees are not folded into swap or trade consideration. They are separate projected legs because downstream disposals attach to a single source leg.
- Each projected acquisition or disposal maps to exactly one source event leg. If one residual quantity comes from multiple current-event legs, it must be split before downstream records are created.
- Fee valuation is event-coupled. If a fee asset also appears as a non-fee projected asset in the same event, the fee inherits that event's EUR-per-unit rate for the asset.
- `DisposalLink.proceeds_total` for a fee leg means implied fair market value in EUR at the event timestamp, not literal cash proceeds received by that fee leg.
- Events can be unbalanced because the system sees only owned wallets and visible imported legs.
- Same-event acquisitions must not fund same-event disposals.

## Phase 1: Quantity Projection

Non-fee legs are considered at the asset level. Visible movement of the same asset between owned accounts cancels out. The surviving residual quantity, if any, becomes the projected acquisition or disposal quantity for that asset. A zero residual means the event did not change owned inventory for that asset.

Explicit fee legs are different. They stay explicit and are projected directly even when the fee asset also appears as a non-fee asset in the same event.

Non-fee anchor assets such as `EUR`, other fiat currencies, and selected stable assets remain part of the non-fee projection. Their special treatment happens in valuation, not in quantity projection.

If one asset residual survives on multiple same-sign current-event legs, phase 1 must split that residual across those legs. That split is not just an implementation detail. Each projected acquisition or disposal maps to exactly one source event leg, so one projected record cannot represent multiple current-event legs at once.

Examples:

- `Wallet A -1 BTC`, `Wallet B +1 BTC` projects nothing for `BTC`
- `Wallet -1 ETH`, `Wallet +1800 USDC` projects one `ETH` disposal and one `USDC` acquisition
- `A -1 ETH`, `B +0.6 ETH`, `C +0.5 ETH` projects only the `+0.1 ETH` residual acquisition split across B and C legs

## Phase 2: Assign EUR Values

Valuation is event-aware. Pure market pricing is not enough on its own because the event itself can carry stronger valuation evidence. Some assets should anchor the event instead of moving with crypto market noise, and some imported events are unbalanced because the system sees only owned wallets.

Phase 2 first resolves non-fee projected assets. The high-level algorithm is:

1. ask the price service for direct EUR rates for the non-fee projected assets
2. if more than one distinct non-fee asset is unpriceable, fail
3. if exactly one distinct non-fee asset is unpriceable, solve it as the remainder needed to make the non-fee event balance
4. keep `EUR`, other fiat currencies, and selected stable assets fixed as valuation anchors
5. proportionally adjust only the remaining non-anchor assets so the non-fee event balances

When both sides of the event contain adjustable non-anchor assets, the adjustment is symmetric and moves both sides toward a midpoint. When only one side contains adjustable assets, that side absorbs the adjustment.

Fees stay structurally separate from non-fee legs and do not participate in the non-fee balancing equation. After non-fee rates are resolved, a fee first tries to inherit the same-event EUR-per-unit rate for the same asset. If that is not available, it falls back to direct pricing.

The phase should produce defensible EUR-per-unit rates that later phases can use directly.

## Failure Boundaries

Projection must fail when automatic valuation cannot produce a defensible result.

Important failure boundaries:

- more than one distinct non-fee asset is unpriceable in the same event
- a valuation anchor asset cannot be priced directly in EUR
- a fee asset appears only in fee legs and cannot be priced in EUR
- a one-sided event relies on direct price service valuation and the price is unavailable
- remainder solving would require negative value
- remainder solving is required but there is not enough known value on the other side to solve it
- a two-sided event contains only anchored assets and their valued totals disagree

## Phase 3: FIFO Matching

FIFO matches each projected non-fiat disposal against older open acquisition lots of the same asset. Fiat anchors do not open or consume FIFO lots. Disposals are processed before acquisitions so that a same-event acquisition residual cannot fund a same-event disposal residual, and a single projected disposal leg may still produce multiple `DisposalLink`s, one for each historical lot fragment consumed by FIFO.

## Consequences of the Model

- Internal transfers do not create fresh tax lots.
- Moving an asset between owned accounts does not reset FIFO because lots are tracked per asset, not per account.
- Fees remain explicit and separately deductible / taxable because they keep their own source-leg identity through `is_fee=True`.
- Fiat and selected stable consideration anchor event valuation instead of being proportionally adjusted together with non-anchor assets. Fiat does this without creating or consuming FIFO lots, while selected stable assets remain lot-tracked.
- Current-event valuation is determined before inventory history is consulted.

## Future Extension: Operator-Supplied Valuation Corrections

Some events will remain impossible to value automatically, especially when multiple distinct non-fee assets are unpriceable in the same event.

For those cases the next step should add operator-supplied valuation overrides for projected acquisitions and disposals. The operator would provide replacement or correction values, and the projector would use those values instead of failing.

This is intentionally deferred for now to keep the first implementation simpler.

The current model already gives stable attachment points for future overrides:

- source event identity is stable through `EventOrigin`
- source leg identity is stable through `leg_key` / `source_leg_ref`
