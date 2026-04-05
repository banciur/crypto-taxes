# Lot Matching Algorithm

This document explains the current `AcquisitionDisposalProjector` algorithm.

## Scope

The projector turns chronologically ordered `LedgerEvent`s into:

- `AcquisitionLot`s
- `DisposalLink`s

It does two logically separate jobs:

1. classify event legs into projected acquisition and disposal quantities
2. match projected disposals against open acquisition lots using FIFO

EUR valuation happens inside the same projector today, but it is conceptually separate from quantity classification and lot matching.

## Inputs and Invariants

- Events must already be sorted chronologically.
- Open lots are tracked per asset, not per account.
- `LedgerLeg.quantity` is never zero.
- `LedgerLeg.is_fee=True` marks an explicit fee leg that keeps its own identity downstream.

## Phase 1: Classify Projected Quantities

For each event:

1. Ignore `EUR` legs for quantity classification.
2. Project all explicit fee legs directly.
   - A negative fee leg becomes a disposal quantity.
   - A positive fee leg would become an acquisition quantity, although typical runtime examples are negative.
3. Group the remaining non-fee, non-EUR legs by `asset_id`.
4. For each asset group, compute the net asset change:
   - `net_quantity = sum(leg.quantity)`
5. Interpret the net quantity:
   - `net_quantity == 0`: nothing is projected for that asset. This is a pure internal transfer for projection purposes.
   - `net_quantity > 0`: project acquisitions totaling `net_quantity`.
   - `net_quantity < 0`: project disposals totaling `abs(net_quantity)`.

### Residual Distribution Across Legs

When one asset group has multiple legs on the surviving side, the residual is split proportionally across those same-sign legs.

Examples:

- `A -1 BTC`, `B +1 BTC`
  - net `0`
  - no acquisition, no disposal

- `A -1 BTC`, `B +0.99 BTC`
  - net `-0.01`
  - one projected disposal of `0.01 BTC`

- `A -1 ETH`, `B +0.6 ETH`, `C +0.5 ETH`
  - net `+0.1`
  - projected acquisition total is `0.1 ETH`
  - split proportionally across `B` and `C`

### Exact Total Preservation

Proportional allocation can create repeating decimals. To preserve exact totals:

- for the first `n - 1` legs, allocate by ratio
- for the last leg, allocate the remaining quantity

This guarantees that the projected quantities sum exactly to the asset residual.

## Phase 2: FIFO Lot Matching

After projected quantities are computed for the event:

1. Process projected disposals first.
2. For each projected disposal:
   - look up the open lots queue for that asset
   - consume from the front of the queue
   - emit one `DisposalLink` per consumed lot fragment
3. After disposals are processed, append projected acquisitions as new open lots for that asset.

Processing disposals before acquisitions is important. It prevents a same-event acquisition residual from incorrectly funding a same-event disposal residual.

## Valuation

For each projected acquisition or disposal:

- prefer a matching EUR leg from the event when that EUR attribution is unambiguous
- otherwise fall back to the injected `PriceProvider`

The current implementation only uses event EUR pricing for non-fee projected quantities when there is a single non-fee projected quantity on that side of the event. This prevents unrelated EUR proceeds from being assigned to separate fee disposals.

## Consequences of the Model

- Internal transfers do not create fresh tax lots.
- Explicit fee legs preserve source-leg identity through `is_fee=True`.
- If upstream omits an explicit fee leg, the projector can still derive the correct residual quantity, but it cannot infer that the residual specifically came from a fee leg.
- Because open lots are tracked per asset, not per account, moving an asset between owned accounts does not reset FIFO history.
