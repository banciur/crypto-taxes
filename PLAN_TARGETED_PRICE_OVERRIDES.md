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

An override is identified by the **`event_origin` of the corrected event it prices**, plus the `asset_id` it applies
to and the EUR per-unit `rate`. It is matched against a corrected event by a direct lookup of that origin:

- The corrected-events stream that valuation runs on (`AcquisitionDisposalProjector.project`) contains either
  passthrough raw events (their own raw origin) or synthetic correction events (origin = `(INTERNAL, correction.id)`,
  built by `ledger_event_from_correction`).
- Each corrected event's `event_origin` uniquely identifies it: passthrough origins are unique, and a replacement's
  synthetic origin is unique per correction — its id is a stable UUID persisted in the durable corrections DB. So an
  override resolves by looking its `event_origin` up in the stream, with no source-set indexing and no dependency on
  the corrections list.

An override resolves only when its `event_origin` **equals** a corrected event's `event_origin`. This deliberately
does **not** follow an event across a re-grouping: if a correction later folds the priced raw event into a replacement
(merge/split) or discards it, the raw origin no longer appears in the stream and resolution raises, so the operator can
delete the override and, if the price is still wanted, re-author it against the new synthetic event. Deleting and
recreating a correction mints a new id, so an override pinned to the old synthetic origin also stops resolving. An
override authored directly against a replacement's synthetic origin keeps resolving as long as that correction exists;
if the replacement later drops the priced asset, the asset-not-present check raises instead.

Opening-balance corrections emit a synthetic corrected event (they carry exactly one leg), so under origin-based
identity they are addressable by that synthetic `(INTERNAL, correction.id)` origin like any other replacement — the
earlier "no sources, not addressable" limitation was a consequence of the source-set model and no longer applies.

### Data model

New durable store `artifacts/price_overrides.db` (sibling to `corrections.db`; never in the disposable
`price_cache.db`):

- `price_overrides`: `id (UUID)`, `origin_location (str)`, `origin_external_id (str)`, `asset_id (str)`,
  `rate_eur (Decimal)`, `note (str | None)`, audit fields. No join table — the target is a single origin.
- A unique constraint on `(origin_location, origin_external_id, asset_id)` allows at most one rate per asset per
  priced event. Two overrides competing for the same asset on the same event are therefore unrepresentable, so
  grouping them for valuation cannot silently drop one.

Domain model `PriceOverride` (in `src/domain/price_override.py`, alongside its validation):
- `event_origin: EventOrigin` — the corrected event being priced; a raw origin or a synthetic
  `(INTERNAL, correction.id)` origin. Unlike `LedgerCorrection.sources`, an `INTERNAL` origin is valid here.
- `asset_id: AssetId` — stored as given (no normalization, consistent with `LedgerLeg.asset_id`).
- `rate_eur: Decimal` — strictly positive; interpreted as EUR value of one unit of `asset_id`, i.e. exactly the
  value `PriceProvider.rate(asset_id, EUR, ts)` would return.
- `note: str | None`.

### Validation rules (re-run on every rebuild)

`validate_overrides(corrected_events, overrides)` looks each override up in the corrected events by `event_origin`.
It needs no corrections list — the override already carries the target origin. Two conditions are problems:

- its `event_origin` matches no corrected event (folded into a replacement, discarded, or its correction deleted),
- `asset_id` is not present among the legs of the event it targets.

Any problem raises a `PriceOverrideValidationError` listing every offending override. Each problem names the
override's id, asset, and targeted origin, so the message is actionable on its own.

`PriceOverrideRepository.rates_by_origin()` regroups the stored rows into
`dict[EventOrigin, dict[AssetId, Decimal]]` for valuation. It needs nothing but the overrides themselves, and the
`(origin, asset)` unique constraint keeps the regroup lossless.

`_build_acquisition_disposal_projection` loads the overrides, validates them against the corrected events, and asks
the repository for the rates — all inside the `ACQUISITION_DISPOSAL` stage, so a `PriceOverrideValidationError` is
recorded as a `FAILED` `SystemState` (consistent with how correction validation fails a run). Validation belongs to
this stage and not to `CORRECTIONS`: overrides do not affect the corrected-event stream, and failing earlier would
also block `WALLET_PROJECTION`, whose balances the operator needs while fixing a stale override.

The `FAILED` `SystemState` is the single channel through which override problems reach the operator; the API does not
re-evaluate them.

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

- [x] **Domain model.** Add `PriceOverride` and `PriceOverrideDraft` in `src/domain/price_override.py`, with a single
  `event_origin: EventOrigin` (raw or `INTERNAL`) and validation: strictly-positive `rate_eur`. Add unit tests for the
  validators.

- [x] **Persistence.** Add `PRICE_OVERRIDES_DB_PATH` to `config`, the single `price_overrides` ORM table under
  `PriceOverridesBase` (origin stored as `origin_location` / `origin_external_id` columns, no join table; unique
  constraint on `(origin_location, origin_external_id, asset_id)`), and a `PriceOverrideRepository` with `list`,
  `create`, `delete`, and `rates_by_origin` under `src/db/`. `main.py` opens the DB by inlining `init_db_session` with
  `PriceOverridesBase.metadata` (same as the sibling corrections DB). Add repository tests (round-trip, delete,
  duplicate rejected by the constraint, `rates_by_origin` grouping).

- [x] **Validation logic.** Add `validate_overrides(corrected_events, overrides)` and
  `PriceOverrideValidationError` to `src/domain/price_override.py`, next to the model. Cover with tests: passthrough
  validates, validates against a replacement's synthetic origin, orphaned-when-folded-into-a-replacement problem,
  asset-not-in-event problem, and that a problem names the override id, asset, and origin.

- [x] **Valuation integration.** Add the `overrides` parameter to `value_projected_event`,
  `_value_non_fee_groups`, and `_value_fee_groups`, consulting overrides before the price provider. Add tests
  covering: override supplies an otherwise-unpriceable non-fee asset, override on a fee-only asset, and an override
  rate flowing through rebalancing/remainder solving.

- [x] **Projector + main wiring.** Thread `overrides_by_event_origin` into `AcquisitionDisposalProjector.project`
  (looked up per event by `event.event_origin`). Give `_build_acquisition_disposal_projection` the
  `PriceOverrideRepository`, and inside it load the overrides, call `validate_overrides` against the corrected events,
  and take the rates from `rates_by_origin()` — so a `PriceOverrideValidationError` fails the `ACQUISITION_DISPOSAL`
  stage. Add a projector test with overrides applied.

- [x] **API.** Add FastAPI endpoints under `src/api/` to list, create, and delete price overrides. The list endpoint is
  a plain dump of the stored overrides — problems reach the operator through the `FAILED` `SystemState`, so the API
  does not re-evaluate them. Map the unique-constraint `IntegrityError` on create to a `409`. Add API tests.

- [ ] **UI.** Add an authoring surface in `ui/` to create an override from a selected event (using its
  `event_origin`) and asset. The form exposes both a total-EUR-value field and a per-unit-rate field; editing either
  recomputes the other from the leg quantity (`rate = value / quantity`, `value = rate * quantity`). Only `rate_eur`
  is sent to the API. Also list and delete overrides. Wire it to the new endpoints.

- [ ] **Docs.** Update `doc/CURRENT.md` (replace the "Operator-supplied valuation overrides … are not implemented"
  non-capability with the implemented behavior and its scope limits), `data/README.md` price-services section, and
  `src/services/README.md` if the validation/valuation seam warrants a note. Keep each detail in its lowest owning
  document.
