# Lot Matching Algorithm

This document explains the current `AcquisitionDisposalProjector` algorithm.

## Scope

The projector turns chronologically ordered `LedgerEvent`s into:

- `AcquisitionLot`s
- `DisposalLink`s

It does three logically separate jobs:

1. classify event legs into projected acquisition and disposal quantities
2. compute values of projected acquisitions and disposals
3. match projected disposals against open acquisition lots using FIFO


## Inputs and Invariants

- Events must already be sorted chronologically.
- Open lots are tracked per asset, not per account.
- `LedgerLeg.quantity` is never zero.
- `LedgerLeg.is_fee=True` marks an explicit fee leg.
- Each event has at most one frozen non-fee EUR value.
- Exact EUR already present in the event must remain unchanged; only the remainder can be distributed across non-EUR legs.
- What is different from typical accounting rules is that events might be unbalanced. System tracks only "own" wallets. Ex. in the event of sending ETH to an external wallet, there will be two ETH legs, fee for transaction cost and real transfer. 

## Phase 1: Classify Projected Quantities

For each event:

1. Group all non-fee legs by `asset_id`, including `EUR`.
2. Project explicit non-EUR fee legs directly.
   - A negative fee leg becomes a disposal quantity.
   - A positive fee leg would become an acquisition quantity, although typical runtime examples are negative.
3. For the non-fee legs in each asset group, compute the net asset change:
   - `net_quantity = sum(leg.quantity)`
4. Interpret the net quantity:
   - `net_quantity == 0`: nothing is projected for that asset. This is a pure internal transfer.
   - `net_quantity > 0`: project acquisitions totaling `net_quantity`.
   - `net_quantity < 0`: project disposals totaling `abs(net_quantity)`.

`EUR` is projected here only so valuation can see exact cash entering or leaving the event. `EUR` projected quantities do not become acquisition lots or disposal links.

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

## Phase 3: FIFO Lot Matching

After projected quantities are computed for the event:

1. Process projected disposals first.
2. For each projected disposal:
   - look up the open lots queue for that asset
   - consume from the front of the queue
   - emit one `DisposalLink` per consumed lot fragment
3. After disposals are processed, append projected acquisitions as new open lots for that asset.

Processing disposals before acquisitions is important. It prevents a same-event acquisition residual from incorrectly funding a same-event disposal residual.

## Consequences of the Model

- Internal transfers do not create fresh tax lots.
- Explicit fee legs preserve source-leg identity through `is_fee=True`.
- Because open lots are tracked per asset, not per account, moving an asset between owned accounts does not reset FIFO history.