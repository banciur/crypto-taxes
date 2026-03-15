# Replacement Corrections Plan

# Plan File Guide

This file is a persistent planning document used across multiple sessions.
It is both documentation for the current task and a tracking tool for progress.
This section is generic guidance for AI and should remain stable across tasks unless the planning format itself is intentionally changed.
During task discussion and implementation, update the task-specific sections below immediately after each decision so they always reflect the current understanding of the work.

- Keep completed work marked with `[x]` so the historical record is preserved.
- Keep remaining work marked with `[ ]` until it is actually finished.
- Continue implementation from the first unchecked item unless the task scope is intentionally reordered.
- Implement steps one by one. After each completed step, stop and let the operator validate the output before continuing to the next step.
- Update the task-specific sections immediately when decisions change; do not wait to batch updates later.
- Keep only information that is relevant to the current task.
- The order of steps should reflect the implementation order.


## Current Task

Implement API and UI support for `Replacement` ingestion corrections so operators can inspect persisted replacements, create new ones from raw-event sources, and remove them safely.

The implementation must stay aligned with the existing backend/domain model:

- replacement sources are raw-event `EventOrigin`s only
- replacement payload is authoritative and independent from the source event payloads
- spam/replacement overlap rules stay enforced before persistence and in the correction pipeline
- API/UI flows must use stable `EventOrigin` identity for raw-event references and must not depend on transient event or leg UUIDs

## Confirmed Constraints

- `Replacement` already exists as a domain correction and persists in the corrections DB as one header row plus source rows plus leg rows.
- The correction pipeline order is fixed: validate spam/replacement interactions, apply spam, apply replacements, append seed events, then sort once.
- Persisted replacement corrections already have stable correction IDs and authoritative timestamps/legs.
- Corrected replacement events already appear indirectly in the corrected lane as synthetic `INTERNAL/replacement:<id>` ledger events, but the corrections lane and HTTP API do not expose replacements directly.
- Current UI mutation state is built around spam markers only.
- Current UI selection is keyed by `EventOrigin`, but it currently allows corrected synthetic events to be selected for spam actions, which is unsafe because only raw events are valid correction sources.

## Proposed API Contract

### Read

- Add `GET /replacement-corrections`.
- Response should expose persisted replacement corrections directly:
  - `id`
  - `timestamp`
  - `sources: EventOrigin[]`
  - `legs: LedgerLeg[]`
- The read endpoint should not require a successful raw-event lookup to render a replacement. The replacement already has its own timestamp, and operators must still be able to inspect/delete an orphaned or invalid replacement if raw data drifts.

### Create

- Add `POST /replacement-corrections`.
- Request body should be a create payload, not the full persisted domain object:
  - `timestamp`
  - `sources`
  - `legs`
- The server should generate the correction ID and any missing leg IDs.
- Before persistence, validate the candidate replacement against:
  - current raw events
  - active spam corrections
  - existing replacement corrections
- Reuse the existing ingestion validation rules so API-time validation matches pipeline-time validation.
- Return a semantic conflict response for domain-rule failures and also protect against a DB uniqueness race on replacement sources.

### Delete

- Add `DELETE /replacement-corrections/{correction_id}`.
- Delete by correction ID, because replacement identity is the correction record, not any one source event.
- Deletion should remain idempotent.

## Proposed UI Shape

### Corrections Lane

- Load replacement corrections alongside seed events and spam markers.
- Add a replacement correction lane item that shows:
  - replacement label
  - authoritative replacement timestamp
  - source origins as traceability metadata
  - authoritative synthetic legs as the primary payload
- For this task, keep the corrected lane behavior functionally unchanged. It already renders the derived synthetic replacement event through the existing corrected-event card, so the missing UI capability is first-class correction display and mutation flow, not corrected-lane rendering.
- A later follow-up could add replacement-specific affordances in the corrected lane, such as clearer internal-origin labeling or a link back from a synthetic corrected event to its originating replacement correction.

### Creation Flow

- Replacement creation should be driven from raw-event selection only.
- The selected events provide the `EventOrigin` source list and editor context, but only cards that still represent raw events are eligible inputs.
- The editor should let the operator set the authoritative replacement payload:
  - replacement timestamp
  - repeatable synthetic legs
  - fee flags per leg
- After save, the UI should persist the correction and refresh the server-rendered corrections lane. The corrected lane still requires a manual pipeline rerun to reflect the new replacement.

### Selection Model

- Keep the selection model close to the current UI: selectable event cards continue to participate in a shared `EventOrigin`-keyed selection state across lanes.
- Add a new `Replace selected` action in the action bar next to the existing spam action.
- Only cards that still represent raw events should be selectable inputs for replacement creation:
  - raw-event cards are eligible
  - event cards from corrections lane that still carry the same raw `EventOrigin` are eligible
  - correction items in the corrections lane are never selectable
  - synthetic corrected events such as `INTERNAL/seed:*` and `INTERNAL/replacement:*` are never selectable
- Replacement creation should perform two layers of validation:
  - UI-side validation for obviously ineligible selections
  - API-side authoritative validation that all submitted sources still map to raw events and are not already covered by spam/replacement corrections
- The corrected lane remains a partial convenience view, not a complete source browser, because spammed raw events disappear there and replaced raw events collapse into one synthetic corrected event. The raw lane is still the only full pre-correction view.

## Main Design Decisions

- Prefer a dedicated replacement API instead of encoding replacements through corrected synthetic events. The correction record is the source of truth; the corrected event is only a derived artifact.
- Prefer delete-by-correction-ID for replacements, unlike spam markers, because one replacement may consume multiple raw events and does not have a single source origin.
- Prefer validating on create but keeping list readable even if persisted corrections become invalid relative to the current raw dataset.
- Create and delete are in scope for this task; edit-in-place is explicitly deferred to a later step.
- Use a structured editor rather than free-form JSON. The payload is still authoritative, but a structured form reduces malformed requests and makes multi-leg authoring less error-prone.
- Treat source order and leg order as non-authoritative for now. Current replacement persistence already reloads sources and legs in repository-defined order, so the first pass should not promise input-order preservation.

## Open Questions

- None at the moment. Implementation can proceed with the agreed create/delete scope, structured editor, and shared selection model with explicit exclusion of synthetic items.

## Steps

- [x] Analyze the existing backend/domain correction flow, persistence, API shape, and UI selection model.

- [x] Resolve whether the existing spam-selection path should also be narrowed to the raw lane in this task.

- [ ] Implement backend replacement correction API endpoints, dependencies, request/response models, and validation/error mapping.

- [ ] Add backend API tests for replacement correction list/create/delete behavior, conflict validation, and idempotent delete semantics.

- [ ] Add UI API modules and types for replacement corrections and load them into the corrections lane.

- [ ] Add a replacement correction card to the corrections lane and wire delete-by-ID from the client.

- [ ] Implement the replacement creation workflow in the UI using raw-event `EventOrigin` sources and authoritative synthetic payload editing.

- [ ] Tighten UI event selection so synthetic correction items and synthetic corrected events are not selectable mutation inputs, while preserving shared `EventOrigin`-based selection for raw-backed event cards.

- [ ] Update `doc/CURRENT.md`, `AGENTS.md`, `data/README.md`, and `ui/README.md` to match the new API/UI behavior once implementation is complete.

- [ ] Verify the backend test suite and the feasible UI checks for the changed paths.
