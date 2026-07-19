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

Process the complete chronological event sequence in explicit phases:

1. Project quantities for every event with `project_event_quantities`.
2. Attempt standard non-fee valuation for every projected event. Store successful rates separately from events that remain unresolved because non-fee rates are unavailable.
3. Build an anchor index from the successful standard valuations, grouped by non-fee `asset_id`. Only this index is eligible for adjacent lookup.
4. Make a second valuation pass over unresolved events. For each event, find the nearest indexed anchor available for each unresolved asset and select the closest asset-anchor pair using the deterministic ordering above.
5. Add that asset's anchor rate to a transient rate map for the target event and retry its non-fee valuation from the beginning. Manual overrides and price-service rates still take precedence.
6. Repeat steps 4–5 for the target event until valuation succeeds. If no anchor exists for any unresolved asset, fail with event context.
7. After all non-fee groups are valued, resolve fee rates using the final same-event non-fee rates and the existing fee rules.
8. After every event is completely valued, perform FIFO matching in chronological order.
9. Propagate valuation failures unrelated to unavailable non-fee rates without starting or continuing adjacent resolution.

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

### Quantity projection pass

`AcquisitionDisposalProjector.project()` needs the complete chronological event sequence because anchor events may be in the past or future.

- Change the input type from `Iterable[LedgerEvent]` to `Sequence[LedgerEvent]`.
- Project quantities once for every event.
- Store each source event together with its projected groups.
- Keep the original chronological sequence for valuation and FIFO application.

### Separate direct-rate discovery from completed valuation

Adjacent resolution must run only when non-fee rates are genuinely unavailable. It must not use a broad `AcquisitionDisposalValuationError` catch because that error also represents failures that adjacency cannot repair.

Refactor valuation so the projector can distinguish:

- non-fee assets whose manual override or price-service rate is unavailable
- a completed standard valuation
- other valuation failures that must propagate

Reuse this rate-discovery logic in standard valuation and target-event retrying. Do not duplicate the manual-override and price-service precedence rules in the projector.

### Standard non-fee valuation pass

Attempt standard non-fee valuation once for every projected event using:

- the event's saved manual overrides
- the price provider at the event timestamp
- same-event remainder solving
- valuation-tier rebalancing

Store successful final non-fee rates by `event_origin`. For events that cannot be standard-valued because rates remain unavailable, store the unresolved asset ids for the adjacent valuation pass.

Build the anchor index only from successful results, grouped by each non-fee asset present in the result. This makes the no-chaining rule structural: events resolved later through adjacency are never added to the index.

Operational price-provider exceptions and valuation failures unrelated to unavailable rates propagate immediately.

### Adjacent valuation pass

Process the events left unresolved by the standard pass. For each target event:

- inspect only indexed anchors for its unresolved assets
- exclude the target event
- choose the closest asset-anchor pair
- add its final rate to the target event's transient rates
- retry non-fee valuation from the beginning
- continue until non-fee valuation succeeds or no eligible anchor remains

The existing remainder solver, valuation tiers, and balancing remain authoritative. The adjacency resolver supplies missing evidence but does not implement a second balancing algorithm.

### Fee valuation and FIFO pass

After every event has final non-fee rates:

- resolve fee rates using the final same-event non-fee rate when the asset is present there
- otherwise use the existing manual-override and price-service fee lookup
- fail if a fee-only asset remains unpriceable
- perform FIFO matching for the completely valued events in chronological order

### Preserve failure behavior

Keep each pass fail-fast and attach event origin and timestamp to valuation and FIFO errors.

Because all valuation finishes before FIFO starts, any valuation failure leaves no newly matched acquisition/disposal output. A FIFO failure still leaves output matched through the last successfully applied event for debugging.

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

- existing direct pricing, overrides, remainder solving, tier rebalancing, fee handling, and FIFO matching rules remain unchanged
- a valuation failure occurs before FIFO and leaves no newly matched projection output
- a FIFO failure retains output through the last successfully matched event
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
3. Add the complete-sequence quantity projection pass.
4. Add the standard non-fee valuation pass and build the anchor index from its successful results.
5. Add the second-pass adjacent resolution with transient borrowed rates.
6. Move fee completion before the chronological FIFO pass.
7. Add one-sided, failure-boundary, no-chaining, and pass-order tests.
8. Run formatting, static checks, and the full data test suite.
9. Update the authoritative domain documentation to match the implemented behavior.
