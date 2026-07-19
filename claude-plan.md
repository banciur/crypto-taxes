# Implementation plan: resolve missing asset prices from adjacent events

## Goal

Allow the acquisition/disposal projection to value an event when its non-fee assets cannot all be priced directly.

Valuation uses the strongest available evidence in this order:

1. a saved manual price override for the asset in the event
2. the price service, including its cache
3. the value implied by the other non-fee assets in the same event when exactly one asset remains unpriced
4. a transient rate borrowed from the nearest event in which the asset can be valued by steps 1–3

After borrowing a rate, retry same-event valuation before borrowing another one. This lets the target event determine the final missing rate whenever it contains enough opposing value.

## Scope

This applies to non-fee projected asset groups. Existing fee valuation remains unchanged: a fee uses the resolved same-event rate for its asset when available and otherwise requires a direct manual or price-service rate.

Adjacent-event rates are projection-time inputs. They are recalculated on every acquisition/disposal rebuild and are not persisted.

Manual `PriceOverride`s remain the only persisted valuation corrections. Their domain model, database schema, repository, API, and UI do not change.

## Definitions

### Standard event valuation

An event is standard-valued using only:

- saved manual overrides targeting that event
- rates returned by the price service at that event's timestamp
- the existing same-event remainder solver when exactly one non-fee asset is unpriced
- the existing valuation-tier rebalancing rules

Standard valuation never borrows rates from adjacent events.

### Resolved event

An event is resolved for adjacency when its non-fee projected groups can be completely standard-valued. Its final rate for an asset may therefore come from a manual override, the price service, same-event remainder solving, or tier rebalancing.

Fee valuation does not determine whether an event can be used as a non-fee anchor.

### Adjacent anchor

An adjacent anchor for an asset is another event that:

- has a non-fee projected group for that asset
- can be standard-valued
- produces a final EUR-per-unit rate for the asset

The nearest anchor is the standard-valued candidate with the smallest absolute timestamp difference from the target event. Candidates may precede or follow the target event.

Sort candidates by absolute timestamp difference. If multiple candidates are equally close, sort by their stable `EventOrigin` (`location`, then `external_id`) to select one deterministically. The event-origin ordering is only a tie-breaker; it does not affect which event is closest in time.

## Resolution algorithm

For each target event:

1. Project its quantities with `project_event_quantities`.
2. Attempt standard valuation.
3. If standard valuation succeeds, continue to FIFO matching.
4. If standard valuation fails because non-fee rates remain unavailable, find the nearest standard-valued anchor available for each unresolved asset.
5. Select the closest anchor across those unresolved assets using the deterministic ordering above.
6. Add that asset's anchor rate to a transient rate map for the target event.
7. Retry standard valuation from the beginning with the saved manual overrides and transient rates available as inputs. Manual overrides and price-service rates still take precedence.
8. Repeat steps 4–7 until standard valuation succeeds.
9. If no anchor exists for any unresolved asset, fail the projection with event context.
10. Propagate valuation failures unrelated to unavailable non-fee rates without starting or continuing adjacent resolution.

The transient map is local to the target event. A borrowed rate is never added to the saved override collection and never makes the target event eligible as an anchor.

For a one-sided event, standard valuation cannot remainder-solve the final missing rate, so adjacent resolution must supply every unavailable rate.

## Structural invariants

1. The precedence order is manual override, price service, same-event resolution, then adjacent borrowing. A transient rate is added only for an asset confirmed to be unavailable from the preceding sources.
2. Adjacent search runs only for genuinely unavailable non-fee rates. Other valuation failures, including broken reference pricing, invalid remainder values, impossible balancing, and missing fee rates, propagate without adjacent search.
3. Anchor events use standard valuation only. Anchor search never recurses.
4. A target event valued with a borrowed rate cannot become an anchor for another event.
5. Borrowed rates exist only for the current projection run and are never persisted.
6. Same-event evidence is preferred over additional borrowed rates by retrying valuation after each borrowed rate.
7. Candidate and anchor selection is deterministic and independent of input iteration order.

## Implementation design

### Prepare projected events and candidate indexes

`AcquisitionDisposalProjector.project()` needs the complete chronological event sequence because anchor events may be in the past or future.

- Change the input type from `Iterable[LedgerEvent]` to `Sequence[LedgerEvent]`.
- Project quantities once for every event.
- Build an index from each non-fee `asset_id` to the projected events containing that asset.
- Keep the original chronological sequence for FIFO application.

### Separate direct-rate discovery from completed valuation

Adjacent resolution must run only when non-fee rates are genuinely unavailable. It must not use a broad `AcquisitionDisposalValuationError` catch because that error also represents failures that adjacency cannot repair.

Refactor valuation so the projector can distinguish:

- non-fee assets whose manual override or price-service rate is unavailable
- a completed standard valuation
- other valuation failures that must propagate

Reuse this rate-discovery logic in standard valuation and target-event retrying. Do not duplicate the manual-override and price-service precedence rules in the projector.

### Memoize standard anchor valuation

Standard valuation of a candidate is a pure result of:

- its projected quantities and timestamp
- the price provider
- its saved manual overrides

Memoize the result by `event_origin` for the duration of one projection. Cache both successful and unresolvable results so repeated searches do not revalue the same candidate.

Operational price-provider exceptions must propagate and must not be cached as an unpriceable result.

### Resolve the target event

When standard valuation reports multiple unavailable non-fee assets:

- inspect only indexed candidate events for those assets
- exclude the target event
- consider only candidates with successful memoized standard valuation
- choose the closest asset-anchor pair
- add its final rate to the target event's transient rates
- retry the existing valuation logic

The existing remainder solver, valuation tiers, balancing, and fee inheritance remain authoritative. The adjacency resolver supplies missing evidence but does not implement a second balancing algorithm.

### Preserve failure behavior

Keep projection fail-fast. If adjacency cannot resolve an event, attach its origin and timestamp to the valuation error and stop before applying that event to FIFO.

Collecting multiple projection failures is outside this change because skipping a failed event can make later FIFO failures misleading.

## Tests

### Valuation behavior

- a manual override wins over a price-service rate
- a price-service rate is used when no manual override exists
- one unavailable asset is solved from opposing same-event value before adjacency is considered
- non-missing valuation errors do not start adjacent search
- fee valuation behavior is unchanged

### Anchor eligibility

- an event priced directly by the service is an anchor
- an event priced by a manual override is an anchor
- an asset remainder-solved within an otherwise standard-valued event is an anchor
- an event requiring an adjacent rate is not an anchor
- an event with resolved non-fee groups remains an anchor even if an unrelated fee cannot be priced

### Anchor selection

- the nearest past anchor is selected
- the nearest future anchor is selected
- absolute distance wins across past and future candidates
- stable event origin provides deterministic tie-breaking between equally close candidates
- events that contain the asset but cannot be standard-valued are skipped

### Target resolution

- with two missing rates, one borrowed rate allows the other to be solved from the target event
- with three or more missing rates, rates are borrowed incrementally until same-event resolution can finish
- a one-sided event borrows every missing rate
- different missing assets may use different anchor events
- resolution fails when no unresolved asset has an eligible anchor
- borrowed rates are not reused as anchors for later events
- borrowed rates are recomputed on a new projection run

### Regression coverage

- existing direct pricing, overrides, remainder solving, tier rebalancing, fee handling, and FIFO behavior remain unchanged
- the known fcbBTC/pfcbBTC sequence completes without persisted derived overrides
- representative one-sided UNI-V2 and RONIN events resolve from adjacent standard-valued events

## Documentation updates

After implementation:

- update `doc/LOT_MATCHING.md` with the valuation resolution order and non-recursive adjacency rule
- update `doc/CURRENT.md` with automatic adjacent-event valuation as implemented behavior
- update `data/README.md` only if projector workflow or component guidance needs additional detail not owned by the domain documents

## Implementation order

1. Add focused tests for standard anchor eligibility and deterministic anchor selection.
2. Refactor non-fee rate discovery so unavailable rates are distinguishable from other valuation failures.
3. Pre-project the event sequence and build the non-fee asset candidate index.
4. Add memoized, non-recursive standard valuation for anchor candidates.
5. Add incremental target-event resolution with transient borrowed rates.
6. Add one-sided, failure-boundary, and no-chaining tests.
7. Run formatting, static checks, and the full data test suite.
8. Update the authoritative domain documentation to match the implemented behavior.
