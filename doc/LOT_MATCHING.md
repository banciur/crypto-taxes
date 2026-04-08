# Lot Matching Algorithm

This document defines the intended `AcquisitionDisposalProjector` algorithm and is the source of truth for its implementation.

## Scope

The projector turns chronologically ordered `LedgerEvent`s into:

- `AcquisitionLot`s
- `DisposalLink`s

It does three jobs:

1. classify event legs into projected acquisition and disposal quantities
2. compute EUR values for projected acquisitions and disposals
3. match projected disposals against open acquisition lots using FIFO

`AcquisitionLot.cost_per_unit` and `DisposalLink.proceeds_total` are both EUR-based values.

## Core Rules

- Events are already sorted chronologically before projection.
- Open lots are tracked per `asset_id`, not per account.
- `LedgerLeg.quantity` is never zero.
- `LedgerLeg.is_fee=True` means the leg is explicit and must stay explicit downstream.
- Only non-fee `EUR` is special. It is treated as an exact authoritative value already present in the event.
- Other fiat assets such as `USD` or `PLN` are not special. They are valued through `PriceProvider` into EUR like any other non-EUR asset.
- Fees are not folded into swap or trade consideration. They are separate projected legs because downstream disposals attach to a single source leg.
- Fee valuation is still event-coupled. If a fee asset also appears as a non-fee projected asset in the same event, the fee inherits that event's EUR-per-unit rate for the asset.
- `DisposalLink.proceeds_total` for a fee leg means implied fair market value in EUR at the event timestamp, not literal cash proceeds received by that fee leg.
- Events can be unbalanced because the system sees only owned wallets and visible imported legs.

## Phase 1: Project Quantities

### Non-fee legs

For each event:

1. Group non-fee legs by `asset_id`, including `EUR`.
2. For each asset group, compute:
   - `net_quantity = sum(leg.quantity)`
3. Interpret the net quantity:
   - `net_quantity == 0`: project nothing for that asset. This is an internal transfer for that asset.
   - `net_quantity > 0`: project acquisitions totaling `net_quantity`.
   - `net_quantity < 0`: project disposals totaling `abs(net_quantity)`.

`EUR` is projected only for valuation. It does not become an `AcquisitionLot` or a `DisposalLink`.

### Explicit fee legs

Explicit fee legs are projected directly and never netted into non-fee legs:

- negative fee leg -> projected disposal
- positive fee leg -> projected acquisition

This is required even when the fee asset matches another non-fee asset in the same event.

### Residual distribution across legs

If an asset residual survives on multiple same-sign source legs, split the projected quantity proportionally across those legs.

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

### Exact total preservation

Proportional allocation can create repeating decimals. To preserve exact totals:

- allocate the first `n - 1` legs proportionally
- allocate the final leg as the remaining quantity

This rule is used everywhere the algorithm splits a total across multiple outputs.

## Phase 2: Compute EUR Values

Phase 2 works on projected quantities from phase 1 plus the projected non-fee `EUR` residual, if any.

Phase 2 has two logical steps:

1. solve EUR values for the non-fee part of the event
2. value explicit fee legs from the event-implied asset rate when possible, otherwise from `PriceProvider`

The goal of phase 2 is:

- each projected acquisition gets an EUR total, then `cost_per_unit = total_value_eur / quantity`
- each projected disposal gets an EUR total, then a per-unit proceeds rate used later when building `DisposalLink`s

### Value sources

There are only three ways to know the EUR value of a projected non-fee component:

1. exact non-fee `EUR` quantity already present in the event
2. direct pricing from `PriceProvider.rate(asset_id, "EUR", timestamp)`
3. remainder solving from the other side of the same event when exactly one distinct non-fee asset is unpriceable

If none of those can determine a value, projection must fail.

### Fee valuation

Fees stay structurally separate from non-fee legs, but they are not always valued independently.

The non-fee portion of the event is solved first. Then each fee leg is valued by this order:

1. if the same `asset_id` appears in a solved non-fee projected bucket in the same event, use that bucket's EUR-per-unit rate
2. otherwise use direct `PriceProvider.rate(asset_id, "EUR", timestamp)`
3. if neither is possible, projection fails

This is important for events such as:

- non-fee disposal: `-10 EXOTIC`
- fee disposal: `-1 EXOTIC`
- non-fee acquisition: `+110 USDC`

If `EXOTIC` has no market price but the non-fee trade implies `11 EUR` per `EXOTIC`, the fee leg must use that same implied rate and therefore receives `11 EUR` of `proceeds_total`.

Fee values are additive on top of the non-fee event consideration. They do not change the balancing equation for the non-fee side of the event.

### Asset-group valuation before leg-level splitting

Valuation is first determined at the projected asset-group level:

- one non-fee acquisition bucket per asset
- one non-fee disposal bucket per asset
- one fee bucket per explicit fee leg

If phase 1 split one asset residual across multiple same-asset legs, that asset-group EUR total is later split across those legs proportionally by projected quantity. This preserves one shared per-unit value for that asset residual.

### Case A: Event contains exact non-fee EUR

If the event has a non-zero projected non-fee `EUR` residual, that `EUR` amount is authoritative.

Authoritative means:

- the `EUR` amount itself is fixed exactly
- it is never replaced by price-service output
- event valuation must respect it when distributing value across non-EUR non-fee legs

This does not mean `EUR` must be the only valued component on its side.

If one side contains `EUR` and other legs, the `EUR` amount stays fixed and the remaining same-side legs are handled normally:

- directly priced if the price service knows them
- solved as the single remainder if they are the only distinct unknown asset

After the fixed and directly priced components are known, the remaining unresolved part of the event absorbs whatever total is required for the non-fee event to balance. That unresolved part can live either on the `EUR` side or on the opposite side, but there may be only one distinct unknown non-fee asset in the whole event.

#### Consequence for multi-leg EUR events

Example:

- acquisitions: `EUR +100`, `TOKEN_A +1`, `TOKEN_B +1`
- disposals: `ETH -1`

Then:

- `EUR +100` stays exactly `100 EUR`
- `TOKEN_A` and `TOKEN_B` are directly priced if possible
- the total acquisition-side EUR value determines the disposal-side total
- if `ETH` is the only disposal asset, its disposal proceeds become that full acquisition-side total

So when one side has multiple legs and one of them is `EUR`, `EUR` stays exact but it does not erase the other legs on that side. It only freezes one part of that side's total.

### Case B: No exact EUR and all non-fee assets are priceable

If the event has no exact `EUR` component and every non-fee asset is directly priceable in EUR:

- value every non-fee projected asset directly from `PriceProvider`
- do not force both sides to balance

This is intentional. Without exact EUR, price-service snapshots are treated as the best available independent valuations.

### Case C: Exactly one distinct non-fee asset is unpriceable

If exactly one distinct non-fee asset in the event cannot be priced directly, solve its EUR total as the remainder required for the non-fee event to balance.

The balancing equation is:

- `total_non_fee_acquisitions_eur = total_non_fee_disposals_eur`

Known terms can come from:

- exact `EUR`
- directly priced non-EUR assets

The single unknown asset receives the remainder needed to satisfy the equation.

Distinct means distinct `asset_id`, not number of projected legs. If an asset appears in both a non-fee leg and a fee leg, it still counts as one asset for valuation purposes and the fee later inherits that asset's solved rate.

This is the fallback used for cases such as:

- swapping a known token into an LP or farm token with no market price
- receiving a known exact `EUR` amount plus one unpriceable token
- spending a known token and receiving one unpriceable token

### Failure cases

Projection must fail when phase 2 encounters any of these cases:

- more than one distinct non-fee asset is unpriceable in the same event
- a fee asset appears only in fee legs and cannot be priced in EUR
- a one-sided event relies on price service valuation and the price is unavailable
- remainder solving produces a negative value
- remainder solving is required but there is not enough known value on the other side to solve it

### One-sided events

Pure inflows or outflows still need EUR valuation.

Examples:

- reward / airdrop / deposit from outside -> acquisition only
- send to outside / burn / execution fee -> disposal only

For those events:

- use direct price service valuation
- if the price is unavailable, fail

There is no balancing fallback because there is no visible non-fee opposite side inside the event.

### How value is distributed across multiple assets

If a known side total must be split across multiple non-EUR assets on the other side:

1. use direct EUR values as weights for every directly priceable asset
2. if exactly one distinct asset on that side is unpriceable, assign that asset the remainder after subtracting all known same-side assets
3. if more than one distinct asset on that side is unpriceable, fail

If all assets on that side are directly priceable and an authoritative total must still be imposed because exact `EUR` is present on the opposite side:

- scale their direct EUR values proportionally so the side total matches the authoritative total

This preserves:

- exact `EUR`
- direct market ratios as the best available weighting
- exact event-side totals

## Phase 3: FIFO Matching

After quantities and EUR values are known for the event:

1. process projected disposals first
2. for each projected disposal:
   - look up the open-lot queue for that `asset_id`
   - consume lots from the front of the queue
   - emit one `DisposalLink` per consumed lot fragment
3. after all disposals are processed, append projected acquisitions as new open lots for that asset

Processing disposals before acquisitions prevents a same-event acquisition residual from funding a same-event disposal residual.

### Acquisition lot value

For each projected acquisition leg with:

- quantity `Q > 0`
- assigned EUR total `V`

emit:

- `AcquisitionLot.quantity_acquired = Q`
- `AcquisitionLot.cost_per_unit = V / Q`

### Disposal link value

For each projected disposal leg with:

- disposal quantity `Q > 0`
- assigned EUR proceeds total `V`

first derive:

- `proceeds_per_unit = V / Q`

Then, when FIFO consumes lot fragments of quantities `q1`, `q2`, ..., `qn`:

- the first `n - 1` links get `qi * proceeds_per_unit`
- the final link gets the remaining proceeds total

This preserves the exact projected disposal proceeds total even when the disposal is split across multiple source lots.

For fee disposals, `proceeds_total` still means the assigned EUR fair market value of the disposed quantity, even when the fee itself had no literal proceeds.

## Consequences of the Model

- Internal transfers do not create fresh tax lots.
- Moving an asset between owned accounts does not reset FIFO because lots are tracked per asset, not per account.
- Fees remain explicit and separately deductible / taxable because they keep their own source-leg identity through `is_fee=True`.
- Exact non-fee `EUR` is preserved as entered consideration, not replaced by market snapshots.

## Future Extension: Operator-Supplied Valuation Corrections

Some events will remain impossible to value automatically, especially when multiple distinct non-fee assets are unpriceable in the same event.

For those cases the next step should add operator-supplied valuation overrides for projected acquisitions and disposals. The operator would provide replacement or correction values, and the projector would use those values instead of failing.

This is intentionally deferred for now to keep the first implementation simpler.

The current model already gives stable attachment points for future overrides:

- source event identity is stable through `EventOrigin`
- source leg identity is stable through `leg_key` / `source_leg_ref`

That should make it possible to persist manual valuation corrections without redesigning the whole projection model.
