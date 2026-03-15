# Plan File Guide

This file is a persistent planning document used across multiple sessions.
It is both documentation for the current task and a tracking tool for progress.
This section is generic guidance for AI and should remain stable across tasks unless the planning format itself is intentionally changed.
During task discussion and implementation, update the task-specific sections below immediately after each decision so they always reflect the current understanding of the work.

- Keep completed work marked with `[x]` so the historical record is preserved.
- Keep remaining work marked with `[ ]` until it is actually finished.
- Continue implementation from the first unchecked item unless the task scope is intentionally reordered.
- Update the task-specific sections immediately when decisions change; do not wait to batch updates later.
- Keep only information that is relevant to the current task.
- The order of steps should reflect the implementation order.

## Current Task

Introduce `Replacement` as a new ingestion-layer correction in the backend/data model.

The intended outcome is:

- Persist manual replacement corrections in the corrections DB.
- Allow one replacement to consume one or more raw events identified by `EventOrigin`.
- Materialize each replacement as one synthetic corrected `LedgerEvent`.
- Remove raw events consumed by replacements from the corrected event stream.
- Fail loudly when replacement references are invalid or overlap with other ingestion-layer corrections.
- Keep the existing downstream/inventory suite passing, but do not redesign downstream behavior as part of this task.

Out of scope for this task:

- API endpoints and UI for creating, editing, or deleting replacements.
- UI logic for proposing a default timestamp from the latest replaced event.
- New downstream tax/inventory semantics beyond whatever is needed to keep tests green.

## Agreed Domain Decisions

- The correction name is `Replacement`.
- `Replacement` belongs to the ingestion-corrections layer, alongside spam and seed corrections.
- `Replacement` may reference raw events only. It does not consume corrected events and does not chain on other corrections.
- A replacement stores explicit synthetic event data: `timestamp` and `legs`.
- Replacement legs are authoritative and may differ completely from the source raw-event legs.
- Replacement events remain subject only to normal ledger invariants already present in the domain: at least one leg and no zero-quantity legs.
- Replacement events may be unbalanced. No balancing or same-asset consistency checks are added.
- Source raw events are referenced by `EventOrigin`, not by raw event UUIDs or leg UUIDs.
- A referenced raw event must exist when corrections are applied; missing references raise and stop processing.
- A raw event may belong to at most one ingestion-layer correction. Overlap between spam and replacement also raises and stops processing.
- The replacement timestamp is stored explicitly. Any future defaulting to "latest replaced event timestamp" is a creation-time helper outside this task and is not persisted as a derived relation.

## Persistence Shape

Replacement corrections live in the corrections DB, not in the main analytics DB.

Persist one logical `Replacement` using three related tables:

- `replacement_corrections`
  - One row per replacement correction.
  - Stores replacement-level data: `id`, `timestamp`.
  - Does not store source rows inline and does not store legs inline.

- `replacement_correction_legs`
  - One row per synthetic leg belonging to a replacement.
  - Stores the same leg payload shape used by `LedgerLeg`: `id`, `replacement_correction_id`, `asset_id`, `quantity`, `account_chain_id`, `is_fee`.
  - These rows are the authoritative payload used to build the synthetic corrected event.

- `replacement_correction_sources`
  - One row per raw event consumed by a replacement.
  - Stores `replacement_correction_id`, `origin_location`, `origin_external_id`.
  - These rows are the provenance and suppression list.

DB constraints to add:

- Unique constraint or unique index on `replacement_correction_sources(origin_location, origin_external_id)` so one raw event cannot be assigned to two active replacements.
- Foreign keys from legs and sources back to `replacement_corrections`.

Deletion model for v1:

- Use hard delete for replacements.
- Do not add tombstones or soft-delete metadata unless a concrete automatic replacement source appears later.

## Backend Shape

Domain model:

- Replace the unused `LinkMarker` in `data/src/domain/correction.py` with `Replacement`.
- `Replacement` should extend `Correction` and `AbstractEvent`.
- `Replacement` should expose `source_event_origins: list[EventOrigin]`.

Repository surface:

- Add a dedicated replacement repository in the corrections persistence layer.
- Minimal repository methods for v1:
  - `create(replacement: Replacement) -> Replacement`
  - `list() -> list[Replacement]`
  - `delete(correction_id: CorrectionId) -> None`

Synthetic corrected event materialization:

- Build a `LedgerEvent` from each replacement during correction application.
- Use `EventOrigin(location=INTERNAL, external_id=f"replacement:{replacement.id}")`.
- Use a dedicated ingestion label for the synthetic event: `replacement_correction`.
- Use the persisted replacement `timestamp` and `legs` exactly as stored.

Correction application order:

1. Load raw events.
2. Load active spam corrections.
3. Load active replacement corrections.
4. Validate the ingestion-corrections layer as a whole.
5. Remove raw events consumed by spam or replacement corrections.
6. Add synthetic replacement events.
7. Add seed events.
8. Sort corrected events deterministically before persisting them.

Validation rules during correction application:

- Every replacement source origin must match exactly one raw event in the imported raw-event set.
- No raw event may be consumed by both spam and replacement corrections.
- No raw event may be consumed by two different replacements.
- Validation failures must raise with descriptive messages and stop the run.

## Test Matrix

Persistence tests:

- Persist and load a replacement with multiple source origins and multiple legs.
- Deleting a replacement removes its header, legs, and source rows.
- DB uniqueness rejects two replacements consuming the same raw `EventOrigin`.

Correction application tests:

- Applying one replacement removes its source raw event and adds one synthetic corrected event.
- Applying one replacement over multiple raw events removes all referenced raw events and adds one synthetic corrected event.
- Replacement payload is used verbatim even when synthetic legs differ from the source raw-event legs.
- Corrected events remain deterministically sorted after spam, replacement, and seed corrections are combined.
- Applying corrections fails when a replacement source does not exist in the raw-event set.
- Applying corrections fails when a raw event is both spammed and replaced.
- Applying corrections fails when two replacements consume the same raw event.

Pipeline wiring tests:

- `main.py` loads replacements from the corrections DB and includes them in the corrected event output.
- Existing downstream tests remain green after replacement support is added.

## Steps

- [x] Lock task scope and agreed replacement semantics in this plan.

- [ ] Update `data/src/domain/correction.py`.
  - Remove `LinkMarker`.
  - Add `Replacement`.
  - Keep naming explicit: `source_event_origins`.

- [ ] Extend the corrections DB schema in `data/src/db/corrections.py`.
  - Add ORM models for replacement headers, legs, and sources.
  - Add the unique source-origin constraint for active replacements.

- [ ] Add replacement persistence support.
  - Implement a repository for `Replacement`.
  - Support `create`, `list`, and `delete`.

- [ ] Add replacement correction application logic under `data/src/corrections/`.
  - Remove referenced raw events.
  - Materialize synthetic replacement events with `INTERNAL/replacement:{id}` origin.
  - Reuse deterministic corrected-event sorting.

- [ ] Add ingestion-layer validation that spans spam and replacement corrections.
  - Fail on missing raw-event references.
  - Fail on spam/replacement overlap.
  - Fail on duplicate replacement consumption.

- [ ] Wire replacement loading and application into `data/src/main.py`.
  - Load replacements from the corrections DB.
  - Apply spam, replacement, and seed corrections in the agreed order.

- [ ] Add tests covering replacement persistence, correction application, validation failures, and main-pipeline wiring.

- [ ] Run `make code_fix` and `make test`.

- [ ] Update documentation after implementation.
  - Update `doc/CURRENT.md`.
  - Update `data/README.md`.
  - Update `/Users/banciur/projects/crypto-taxes/AGENTS.md` if the documented correction layers or backend guidance change.
