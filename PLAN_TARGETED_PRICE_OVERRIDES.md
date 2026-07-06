# Plan File Guide

This file is a persistent planning document used across multiple sessions.
It is both documentation for the current task and a tracking tool for progress.
This section is generic guidance for AI and should remain stable across tasks unless the planning format itself is intentionally changed.
When creating a task-specific plan from this template, keep the full guide section intact so future sessions can still see the operating rules.

This file has two phases:

**Planning phase** — before any implementation begins. The agent's role is to actively help prepare the plan by asking all necessary questions upfront, challenging vague requirements, and ensuring every step is unambiguous before execution starts. All open questions should be surfaced and resolved in this phase, not during implementation. The resulting plan should read as an execution contract, not a brainstorming record. The phase ends when the operator explicitly confirms the plan is ready for execution.

**Execution phase** — once the plan is confirmed. The agent switches to a focused executor role:
- Implement steps one by one. After each completed step, stop and let the operator validate before continuing.
- Steps should be very precise and specific. Decisions belong in the planning phase, not here.
- If anything is unclear or ambiguous, stop and ask the operator. Do not make assumptions.
- Only implement the behavior explicitly described in the steps. Do not add new features or behavior changes that are not part of the plan.
- While executing, act as a senior developer — improve the quality of the code you touch: refactor, remove duplication, simplify complexity, improve naming, apply better patterns, and leave code cleaner than you found it.
- Such refactoring is allowed, but it must never be silent: explicitly mention any improvement you make when reporting the completed step, so the operator can review it.
- Keep completed work marked with `[x]` so the historical record is preserved.
- Keep remaining work marked with `[ ]` until it is actually finished.
- Update the task-specific sections immediately when understanding changes; do not batch updates.

## Plan Content Rules

Task-specific plan sections must describe only the implementation target and the work required to reach it.

Use positive, executable statements:
- Prefer "Add `X` after `Y`"
- Avoid things like "Do not add a CLI flag."
- Avoid "No rollout mode is planned."
- Avoid documenting speculative alternatives once a decision is made.

Resolved decisions must be folded into the relevant task, flow, requirements, or steps. Do not keep a decision log unless the operator explicitly asks for one.

Keep open questions separate from implementation requirements. Remove each open question once answered and update the concrete plan text accordingly.

Do not add non-features, future possibilities, rejected options, or defensive "do not do X" instructions unless they are necessary to prevent a likely destructive or incorrect implementation.

Plan steps should be complete work units:
- Each step should produce a coherent, reviewable change.
- Each step should be small enough to implement and validate independently.
- Each step should be suitable for a separate commit when practical.
- A step may span code, tests, cleanup, and documentation when those changes are required to complete one logical work item.
- Avoid steps that mix unrelated behavior changes in one item.

## Current Task

Add operator-supplied **targeted price overrides**: a manual EUR per-unit rate for a specific asset in a
specific corrected event, so events the market backend cannot price (or prices wrongly) can be valued by hand.

### Domain overview

An override is identified by the **set of raw source `EventOrigin`s** of the corrected event it prices, plus the
`asset_id` it applies to and the EUR per-unit `rate`. It is matched against a corrected event by that event's own
source set:

- The corrected-events stream that valuation runs on (`AcquisitionDisposalProjector.project`) contains either
  passthrough raw events (source set = `{own raw origin}`) or synthetic correction events (origin =
  `(INTERNAL, correction.id)`, built by `ledger_event_from_correction`; source set = the raw origins the correction
  claimed).
- Every raw origin is claimed by at most one correction (DB-enforced by the unique index
  `uq_ledger_correction_sources_active_origin`), and passthrough origins are unique, so each source set identifies at
  most one corrected event with no collisions.

An override resolves only when its source set **exactly equals** a corrected event's source set. This deliberately
does **not** follow an event across a re-grouping: if a correction later merges more raw events into the priced event,
splits it, or discards it, the override's set no longer matches and resolution raises so the operator can delete it
and, if the price is still wanted, re-author it against the new event. An exact-source replacement (a correction that
claims precisely the override's source set) still matches — the source set still uniquely identifies the event and a
per-unit rate stays valid; if that replacement drops the priced asset, the asset-not-present check raises instead.

Opening-balance corrections have no sources, so they are not addressable by this feature — which is the intended
limitation, not a bug to work around.

### Data model

New durable store `artifacts/price_overrides.db` (sibling to `corrections.db`; never in the disposable
`price_cache.db`):

- `price_overrides`: `id (UUID)`, `asset_id (str)`, `rate_eur (Decimal)`, `note (str | None)`, audit fields.
- `price_override_sources`: `(override_id, origin_location, origin_external_id)`.

Domain model `PriceOverride`:
- `sources: frozenset[EventOrigin]` — non-empty; may not contain `INTERNAL` origins (only raw origins are valid,
  same rule as `LedgerCorrection.sources`).
- `asset_id: AssetId` — normalized upper-case.
- `rate_eur: Decimal` — strictly positive; interpreted as EUR value of one unit of `asset_id`, i.e. exactly the
  value `PriceProvider.rate(asset_id, EUR, ts)` would return.
- `note: str | None`.

### Resolution rules (re-run on every rebuild)

`resolve_price_overrides(corrected_events, corrections, overrides)` indexes corrected events by their source set
(`frozenset[EventOrigin] -> LedgerEvent`) and returns `by_event_origin: dict[EventOrigin, dict[AssetId, Decimal]]`,
keyed by the origin of the corrected event each override resolves to.

For each override, these conditions are surfaced as resolution problems:
- its source set matches no corrected event (unclaimed-but-absent, claimed by a discard, or the event was re-grouped
  so its current source set differs — merge/split),
- `asset_id` is not present among the resolved event's legs,
- another override already prices the same `asset_id` on the same resolved event (conflict).

A resolution problem aborts the `ACQUISITION_DISPOSAL` stage with a `PriceOverrideResolutionError` that lists every
offending override, recorded as a `FAILED` `SystemState` (consistent with how correction validation fails a run).

### Valuation integration

`value_projected_event` gains a per-event `overrides: Mapping[AssetId, Decimal] = {}`. In both
`_value_non_fee_groups` and `_value_fee_groups`, an asset present in `overrides` uses the override rate **instead of**
calling `price_provider.rate`; every other asset is unchanged. The override rate is then treated as an ordinary known
rate, so it participates in mid-point rebalancing and remainder solving exactly like a fetched rate. This additively
also resolves today's hard-error cases (a fee-only unpriceable asset; two unpriceable non-fee assets in one event)
whenever an override supplies one of the missing rates.

Overrides are authored in the UI and take effect on the next pipeline rerun, the same author-then-rerun loop used by
corrections.

## Steps

- [x] **Domain model.** Add `PriceOverride` (and a `PriceOverrideDraft` if the create path needs one) under
  `src/domain/`, with validation: non-empty `sources`, no `INTERNAL` origins in `sources`, upper-cased `asset_id`,
  strictly-positive `rate_eur`. Add unit tests for the validators.

- [x] **Persistence.** Add `PRICE_OVERRIDES_DB_PATH` to `config`, the `price_overrides` / `price_override_sources`
  ORM tables, an init function, and a `PriceOverrideRepository` with `list`, `create`, and `delete` under `src/db/`.
  Add repository tests (round-trip, source set persistence, delete).

- [x] **Resolution logic.** Add `resolve_price_overrides(corrected_events, corrections, overrides)` and
  `PriceOverrideResolutionError` in the acquisition/disposal domain package. Cover with tests: passthrough resolve,
  replacement resolve (override follows a raw origin into its replacement's synthetic event), discard/unresolved
  problem, split-across-events problem, and asset-not-in-event problem.

- [ ] **Valuation integration.** Add the `overrides` parameter to `value_projected_event`,
  `_value_non_fee_groups`, and `_value_fee_groups`, consulting overrides before the price provider. Add tests
  covering: override supplies an otherwise-unpriceable non-fee asset, override on a fee-only asset, and an override
  rate flowing through rebalancing/remainder solving.

- [ ] **Projector + main wiring.** Thread `overrides_by_event_origin` into `AcquisitionDisposalProjector.project`
  (looked up per event by `event.event_origin`). In `src/main.py`, load overrides, call `resolve_price_overrides`
  against the corrected events and corrections before projection, pass the result to the projector, and let a
  `PriceOverrideResolutionError` fail the `ACQUISITION_DISPOSAL` stage. Add a projector test with overrides applied.

- [ ] **API.** Add FastAPI endpoints under `src/api/` to list, create, and delete price overrides, returning the
  stable override identity and its resolved status where available. Add API tests.

- [ ] **UI.** Add an authoring surface in `ui/` to create an override from a selected event (supplying its source
  origins) and asset. The form exposes both a total-EUR-value field and a per-unit-rate field; editing either
  recomputes the other from the leg quantity (`rate = value / quantity`, `value = rate * quantity`). Only `rate_eur`
  is sent to the API. Also list and delete overrides. Wire it to the new endpoints.

- [ ] **Docs.** Update `doc/CURRENT.md` (replace the "Operator-supplied valuation overrides … are not implemented"
  non-capability with the implemented behavior and its scope limits), `data/README.md` price-services section, and
  `src/services/README.md` if the resolution/valuation seam warrants a note. Keep each detail in its lowest owning
  document.
