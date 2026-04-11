# Acquisition/Disposal Projector Plan

This file tracks the implementation work needed for the projector to satisfy the target model described in `../doc/LOT_MATCHING.md`.

## Goal

Finish the valuation part of the projector so the code matches the target lot-matching model without overcomplicating the phase interfaces.

## Current Snapshot

- Quantity projection already follows the intended asset-level approach: non-fee legs are netted per asset, explicit fee legs stay explicit, and non-fee `EUR` is kept separate as event-level valuation evidence.
- Valuation currently supports direct pricing for all non-fee projected assets, plus the special case where exact non-fee `EUR` is present and there is exactly one non-fee asset bucket.
- Fee valuation already reuses the non-fee asset rate when that asset was solved in the same event, otherwise it falls back to direct pricing.
- FIFO already consumes open lots before appending same-event acquisitions.
- FIFO still does not preserve the exact projected disposal total across multiple consumed lot fragments. Keep the existing TODO in place and implement that later.

## Design Constraints

- Keep the three phase boundaries intact: quantity projection, valuation, then FIFO.
- Keep the valuation output simple and close to the direct outcome of valuation.
- `value_projected_event` should continue to return a plain dict that later phases can consume directly.
- Prefer `dict[AssetId, Decimal]` of EUR-per-unit rates over introducing richer valuation result objects unless a hard constraint proves that impossible.
- Do not introduce bucket-total return objects just to support the missing valuation cases.
- Use richer internal calculations only if needed, then collapse them back to the simple returned dict.
- Do not redesign FIFO as part of the valuation work.

## Remaining Valuation Requirements

The code still needs to satisfy these target behaviors:

- Exact non-fee `EUR` remains authoritative even when that side of the event also contains other assets.
- If exact `EUR` is present and the other relevant non-fee assets are directly priceable, the event must respect the authoritative `EUR` amount rather than ignoring it.
- If exactly one distinct non-fee asset in the event is unpriceable, solve that asset as the remainder required for the non-fee event to balance.
- If more than one distinct non-fee asset is unpriceable, fail.
- One-sided events still need EUR valuation and therefore require direct pricing.
- Fee legs do not participate in the non-fee balancing equation.
- Fee legs must inherit the solved same-event rate for the same asset when available, otherwise use direct pricing.
- Fail when remainder solving would produce a negative value or when there is not enough known value to solve the remainder.

## Mismatch With Current Code

The main gap is in `src/domain/acquisition_disposal/valuation.py`.

- The current implementation only handles:
  - exact non-fee `EUR` with exactly one non-fee asset bucket
  - direct pricing for every non-fee asset bucket
- It does not yet implement:
  - authoritative exact-`EUR` handling for multi-asset events
  - remainder solving for one unpriceable distinct non-fee asset
  - failure logic around unsupported remainder scenarios

## Suggested Implementation Stages

### Stage 1: Lock the Target With Tests

Add focused projector valuation tests for:

- exact `EUR` plus one non-fee asset
- exact `EUR` plus multiple same-side assets
- all non-fee assets directly priceable with no exact `EUR`
- exactly one distinct unpriceable non-fee asset solved by remainder
- more than one distinct unpriceable non-fee asset failing
- one-sided acquisition or disposal requiring direct pricing
- fee legs excluded from non-fee remainder solving
- fee asset inheriting same-event non-fee rate
- fee-only asset falling back to direct pricing
- negative or unsupported remainder failing

### Stage 2: Expand the Non-Fee Valuation Solver

Refactor non-fee valuation so it can:

- identify directly priced non-fee assets
- identify whether exact non-fee `EUR` is present
- count distinct non-fee unknown assets
- solve the single-unknown remainder case
- respect authoritative exact `EUR` when it is present
- exclude fee legs from non-fee balancing
- produce final EUR-per-unit rates keyed by `asset_id`

This stage should still return the same plain dict shape from `value_projected_event`.

### Stage 3: Finish Fee Valuation On Top of the Solved Non-Fee Rates

After the non-fee solver is expanded:

- reuse solved non-fee rates for matching fee assets
- fall back to direct pricing only when there is no same-event solved rate
- fail explicitly when a fee-only asset cannot be priced

### Stage 4: Leave FIFO Precision Work For a Later Pass

Do not mix the FIFO exact-proceeds-fragment work into the valuation refactor. The valuation pass should end once the code can assign the correct event-level rates. Exact fragment remainder preservation in FIFO remains a separate later change.

## Not In Scope For This Pass

- operator-supplied valuation overrides
- redesigning projector output models
- changing FIFO fragment proceeds preservation
