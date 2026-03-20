# Plan File Guide

This file is a persistent planning document used across multiple sessions.
It is both documentation for the current task and a tracking tool for progress.
This section is generic guidance for AI and should remain stable across tasks unless the planning format itself is intentionally changed.
When creating a task-specific plan from this template, keep the full guide section intact so future sessions can still see the operating rules.

This file has two phases:

**Planning phase** - before any implementation begins. The agent's role is to actively help prepare the plan by asking all necessary questions upfront, challenging vague requirements, and ensuring every step is unambiguous before execution starts. All open questions should be surfaced and resolved in this phase, not during implementation. The phase ends when the operator explicitly confirms the plan is ready for execution.

**Execution phase** - once the plan is confirmed. The agent switches to a focused executor role:
- Implement steps one by one. After each completed step, stop and let the operator validate before continuing.
- Steps should be very precise and specific. Decisions belong in the planning phase, not here.
- If anything is unclear or ambiguous, stop and ask the operator. Do not make assumptions.
- Only do what is explicitly described in the steps. Do not add improvements or fixes that are not mentioned.
- While executing, act as a senior developer - improve code quality as you go: refactor, remove duplication, simplify complexity, improve naming, apply better patterns, and leave code cleaner than you found it.
- Keep completed work marked with `[x]` so the historical record is preserved.
- Keep remaining work marked with `[ ]` until it is actually finished.
- Update the task-specific sections immediately when understanding changes; do not batch updates.


## Current Task

Replace the three current correction concepts (`Spam`, `Replacement`, `SeedEvent`) with one unified `LedgerCorrection` model and one unified correction pipeline.

The intended outcome is:
- one correction domain type in `data/` with shape-driven behavior instead of separate spam/replacement/seed classes
- one corrections persistence model with active correction rows, source rows, leg rows, and tombstones represented by soft-deleted source-backed correction rows
- no runtime seed CSV loading path; opening balances become normal persisted corrections created through the unified corrections API
- existing raw-source ownership rules preserved: one raw `EventOrigin` may belong to at most one active correction
- Moralis auto-generated corrections continue to respect deleted-source tombstones
- API and UI contract updated, so the corrections lane loads one unified correction item/feed, while the raw/corrections/corrected page structure stays the same
- correction edit/update flows are out of scope for this task, but schema/model design must not block them later

### Confirmed Semantics

- `LedgerCorrection` stores `id`, `timestamp`, `sources`, `legs`, `price_per_token`, and `note`
- `timestamp` and `legs` live directly on `LedgerCorrection`; do not embed an `AbstractEvent` field
- shape determines meaning:
  - `sources != []` and `legs == []` => discard correction
  - `sources != []` and `legs != []` => replacement correction
  - `sources == []` and `legs != []` => opening-balance correction
  - `sources == []` and `legs == []` => invalid
- source-backed corrections may consume one or more raw events
- source-backed corrections must not contain duplicate `sources`
- `sources` must reference raw events only; `EventLocation.INTERNAL` is invalid in `sources`
- any correction with `sources` defaults its `timestamp` to the latest matched source timestamp on creation, but the user may override it
- source-less corrections are limited to exactly one leg
- source-less corrections must use a positive non-fee leg; negative or fee opening-balance corrections are out of scope for this refactor
- source-less corrections always require an explicit `timestamp`
- UI-created source-less corrections should default that `timestamp` to "now" but keep it user-editable
- importer/script-created source-less corrections may use `2000-01-01T00:00:00Z` when importing historical opening balances
- `price_per_token` is meaningful only for source-less corrections and is nullable:
  - `NULL` means the opening-balance price is unknown or unset
  - `0` is a meaningful explicit value when the asset was worthless
  - source-backed corrections ignore it and persist `NULL`
- `note` is fully user-editable; user-visible text is not a reliable source of machine behavior
- tombstones are persistence-only concerns, not fields on the active `LedgerCorrection` domain object
- synthetic corrected events are emitted only for corrections with legs
- synthetic corrected events use `EventLocation.INTERNAL`, `event_origin.external_id = str(correction.id)`, and ingestion `ledger_correction`
- existing seed CSV entries will not be migrated from file-backed storage; they can be re-added manually after rollout

### Persistence Rules

- Active domain/repository reads return only active `LedgerCorrection` records
- Tombstones stay in the corrections persistence layer and are represented by soft-deleted source-backed correction rows that remain queryable for recreation suppression
- The unified persistence model must support:
  - correction header rows with soft-delete support
  - zero or more source rows per correction
  - zero or more leg rows per correction
  - source uniqueness across active non-deleted corrections
  - soft-deleted source-backed corrections remaining queryable by source for Moralis recreation checks
- deleting a source-backed correction soft-deletes it and retains its source rows for Moralis suppression checks
- deleting a source-less opening-balance correction does not create tombstones
- tombstones suppress only automatic Moralis recreation; they do not block manual creation of a new correction for the same source
- Moralis auto-generation should treat a tombstoned `(location, external_id)` source as occupied and must not recreate it
- manual correction creation ignores tombstones and only validates against other active corrections
- Because `note` is user-editable, any auto-generation or tombstone decision that must survive note edits belongs in persistence behavior, not in the domain object shape

### Deferred Update Semantics

- correction edit/update flows are not implemented in this task
- schema and repository design must still allow future source replacement where removed old sources become free after the update commits
- when update flows are implemented later, changing `sources` must revalidate against all other active corrections before commit

### Migration Scope

- Preserve existing persisted spam and replacement corrections by migrating them into the new unified corrections schema
- Preserve existing correction ids where practical when migrating spam and replacement corrections
- Do not migrate legacy seed CSV inputs into the new schema automatically
- Migrated spam/discard corrections derive their `timestamp` from the matched raw event timestamp
- Migration must fail loudly if a spam/discard correction cannot be matched to exactly one raw event for timestamp derivation
- Remove the runtime seed CSV loading path after the unified correction flow is in place
- Deliver migration as a one-off script, not as an automatic startup/schema migration

## Steps

- [x] Finalize `LedgerCorrection` semantics, invariants, corrected-event provenance, migration rules, and task scope with the operator.

- [ ] Introduce the target `LedgerCorrection` domain model in `data/src/domain/` and remove `Spam`, `Replacement`, and `SeedEvent` from correction-domain usage. Encode only the agreed invariants:
  - forbid empty `sources` plus empty `legs`
  - require exactly one positive non-fee leg when `sources` is empty
  - forbid duplicate `sources`
  - forbid `EventLocation.INTERNAL` in `sources`
  - keep `price_per_token` nullable for source-less corrections only

- [ ] Add a unified helper that converts a `LedgerCorrection` with legs into a synthetic `LedgerEvent`:
  - use `EventLocation.INTERNAL`
  - use `str(correction.id)` as `event_origin.external_id`
  - use ingestion `ledger_correction`

- [ ] Replace the current multi-stage correction validation with unified `LedgerCorrection` validation:
  - every claimed source must match exactly one raw event when a correction is validated against raw events
  - no raw source may be claimed by more than one active correction
  - source-less corrections bypass raw-source existence checks
  - duplicate sources inside one correction are invalid
  - `INTERNAL` sources are invalid

- [ ] Replace the current multi-stage correction application code with one unified ledger-correction application flow in `data/src/corrections/`:
  - validate correction shapes and source ownership
  - remove all raw events claimed by source-backed corrections
  - emit synthetic corrected events only for corrections with legs
  - preserve current final sort behavior over corrected events

- [ ] Design the unified corrections persistence schema in `data/src/db/`:
  - one correction header table with soft-delete support
  - one correction sources table
  - one correction legs table
  - deleted source-backed corrections act as tombstones through soft-deleted rows
  - source uniqueness enforced for active non-deleted corrections

- [ ] Implement repository behavior for the unified schema:
  - list active corrections ordered by `timestamp DESC, id DESC`
  - create corrections with zero or more sources and zero or more legs
  - delete source-backed corrections by soft-deleting them while preserving tombstone behavior
  - delete source-less opening-balance corrections without creating tombstones
  - expose any tombstone lookup API needed by the Moralis importer without leaking persistence-only fields into the active domain object

- [ ] Write the one-off migration script from existing correction storage:
  - map `spam_corrections` rows to source-backed corrections with no legs
  - map `replacement_corrections` rows to source-backed corrections with legs
  - preserve existing correction ids where practical so downstream references and deletes stay stable
  - derive migrated spam/discard timestamps from matched raw event timestamps
  - fail loudly if a spam/discard correction cannot be matched to exactly one raw event
  - carry forward deleted-spam suppression behavior into the new tombstone representation
  - do not migrate legacy seed CSV inputs

- [ ] Remove the file-backed seed flow from the runtime pipeline:
  - stop loading seeds from `artifacts/seed_lots.csv` in `data/src/main.py`
  - remove seed-event persistence and correction-application code paths that only exist for CSV-backed seeds
  - keep opening-balance creation in the unified corrections repository/API instead

- [ ] Update Moralis importer integration so automatic correction creation uses the unified correction repository:
  - auto-created possible-spam events become source-backed corrections with no legs
  - importer must skip raw origins already claimed by an active correction
  - importer must also respect deleted-source tombstones so previously deleted auto-generated corrections are not recreated

- [ ] Design the unified API request/response shape for one correction resource that covers discard, replacement, and opening-balance cases
  - use one create payload shape and one list item shape
  - delete uses `correction_id` only
  - keep request/response shapes explicit and stable for the UI
  - do not implement correction update endpoints in this task

- [ ] Update API surface in `data/src/api/` to expose unified corrections:
  - replace separate spam/replacement endpoints with unified correction list/create/delete endpoints
  - remove the seed-events endpoint
  - return correction lists ordered by `timestamp DESC, id DESC`

- [ ] Rewrite data-layer tests around the unified model:
  - domain validation tests
  - correction application tests
  - repository tests
  - API tests
  - migration tests covering spam and replacement carry-forward plus deleted-source suppression behavior

- [ ] Update UI types and API modules to consume the unified correction resource

- [ ] Update correction rendering and actions to consume one unified correction item/feed while preserving the existing three-column timeline layout:
  - raw lane unchanged
  - corrected lane unchanged except for unified corrected-event provenance
  - corrections lane loads one unified correction feed, renders shape-driven states for discard, replacement, and opening balance, and displays newest timestamps first
  - correction create/remove flows match the new unified API
  - correction edit flows remain out of scope

- [ ] Remove legacy correction code paths
  - delete old spam/replacement/seed-specific modules that are no longer used

- [ ] Update documentation for the unified correction model in the same change set:
  - `data/README.md`
  - `ui/README.md`
  - `doc/CURRENT.md`
  - `AGENTS.md`
  - any local README files under touched directories if the behavior described there changes
