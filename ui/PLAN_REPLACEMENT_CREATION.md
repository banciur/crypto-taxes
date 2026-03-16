# Replacement Creation UI Plan

# Plan File Guide

This file is a persistent planning document used across multiple sessions.
It is both documentation for the current task and a tracking tool for progress.
This section is generic guidance for AI and should remain stable across tasks unless the planning format itself is intentionally changed.
When creating a task-specific plan from this template, keep the full guide section intact so future sessions can still see the operating rules.
During task discussion and implementation, update the task-specific sections below immediately after each decision so they always reflect the current understanding of the work.

- Keep completed work marked with `[x]` so the historical record is preserved.
- Keep remaining work marked with `[ ]` until it is actually finished.
- Continue implementation from the first unchecked item unless the task scope is intentionally reordered.
- **IMPORTANT** Implement steps one by one. After each completed step, stop and let the operator validate the output before continuing to the next step
- Update the task-specific sections immediately when decisions change; do not wait to batch updates later.
- Keep only information that is relevant to the current task.
- The order of steps should reflect the implementation order.

## Current Task

Implement the remaining UI work for replacement corrections:

- create replacement corrections from raw-event `EventOrigin` selections
- tighten event selection so only raw-backed events participate in spam/replacement mutations
- refresh the server-rendered page after correction mutations so the corrections lane updates immediately

This plan intentionally excludes backend work. The replacement correction API already exists and is treated as the source of truth for create/list/delete semantics.

## Confirmed Constraints

- Replacement creation is driven by raw-event `EventOrigin` identities, not event UUIDs or leg UUIDs.
- The replacement payload is authoritative. Selected source events provide traceability and editing context only.
- The backend create payload requires:
  - `timestamp`
  - `sources`
  - `legs`
- The backend create payload accepts legs without client-assigned IDs; the server generates missing leg IDs on create.
- The backend returns semantic `409` responses when:
  - a source does not map to exactly one raw event
  - a source overlaps with spam
  - a source is already consumed by another replacement
- The corrected lane already renders derived synthetic replacement events with `INTERNAL/replacement:<id>` origins.
- Synthetic corrected events are not valid mutation inputs and must not remain selectable in the UI.
- Current client state is centered in `ui/src/components/Events/Events.tsx`.
- Current page data is server-rendered in `ui/src/app/page.tsx`, so mutation success should use `router.refresh()` instead of duplicating server grouping logic on the client.

## Scope Decisions

- Use a structured modal editor for the first pass.
- Keep creation and deletion in the same page-level action flow managed by `Events.tsx`.
- Fix spam-selection eligibility as part of this task instead of leaving the current unsafe behavior in place.
- Do not implement replacement editing in place.
- Do not add special corrected-lane affordances beyond removing invalid selection controls from synthetic events.
- For initial editor defaults:
  - if one source event is selected, prefill timestamp and legs from that event
  - if multiple source events are selected, prefill only the source list and require the operator to author timestamp and legs explicitly

## Design Outline

### Selection model

- Replace the current `ReadonlyMap<string, EventOrigin>` selection result with a richer raw-backed selection record that includes:
  - `eventOrigin`
  - source `timestamp`
  - source `legs`
- Treat selectable cards as:
  - all `raw-event` items
  - `corrected-event` items only when `eventOrigin.location !== "INTERNAL"`
- Treat non-selectable items as:
  - all correction lane items
  - corrected synthetic seed events
  - corrected synthetic replacement events
- Only render a checkbox for selectable items so the UI no longer implies invalid actions are supported.

### Replacement editor

- Add a dedicated client component under `ui/src/components/Events/` for replacement creation.
- The editor should show:
  - selected source origins as read-only metadata
  - authoritative replacement timestamp input
  - repeatable leg rows with `assetId`, `accountChainId`, `quantity`, `isFee`
  - add/remove leg controls
  - client-side validation for missing timestamp, empty legs, zero/blank quantities, and blank required fields
- Keep the payload editor structured; do not expose free-form JSON.

### Accounts data

- The editor needs the full account list for the account selector, not just display-name lookup.
- Load accounts on the server and expose them through a client context/provider near the existing account names provider.

### Mutation flow

- Add `createReplacementCorrection` to `ui/src/api/replacementCorrections.ts`.
- Improve API error propagation enough for the editor to show backend `409` detail text without parsing opaque error strings in the component.
- On successful create/delete:
  - clear selection if applicable
  - close the modal if applicable
  - surface success feedback
  - call `router.refresh()` so the corrections lane reloads from the server
- Keep the existing message that the corrected lane still requires a manual pipeline rerun.

## Risks And Watchpoints

- Changing selection types will touch multiple layers: selection hook, action bar, date section, lane item, and event card rendering.
- `router.refresh()` can invalidate the current selection state; success handlers should clear local selection first to avoid stale UI state during refresh.
- The replacement editor must not rely on preserving leg order or source order beyond what the backend currently guarantees.
- Client-side validation should stay lightweight and defer rule enforcement about raw/spam/replacement overlap to the backend.

## Open Questions

- None currently. The modal-based first pass and single-source prefill behavior are assumed for implementation unless the operator changes direction.

## Steps

- [ ] Introduce a dedicated replacement-creation plan reference in the broader UI plan if needed so active tracking is not split ambiguously.

- [ ] Refactor the selection model in `ui/src/components/Events/` to return raw-backed selectable event records instead of bare `EventOrigin` values.

- [ ] Tighten selectable eligibility so synthetic corrected events and all correction-lane items never render mutation checkboxes.

- [ ] Update the spam action flow to consume the new selection model while preserving current behavior for valid raw-backed events.

- [ ] Add client-side accounts context/data plumbing so replacement forms can render account selectors from the existing server-loaded accounts dataset.

- [ ] Extend replacement correction API helpers and shared UI types to support create payloads and structured API error handling.

- [ ] Implement a replacement editor modal with source summary, timestamp input, repeatable leg rows, and lightweight client-side validation.

- [ ] Add the `Replace selected` action to the action bar and wire it to open the editor from the current selection.

- [ ] Implement replacement create submission, conflict/error feedback, success feedback, selection reset, and `router.refresh()` after successful create.

- [ ] Update existing delete success paths for spam and replacement corrections to use `router.refresh()` so the corrections lane reflects removals immediately.

- [ ] Update `ui/README.md`, `doc/CURRENT.md`, `data/README.md`, and `AGENTS.md` after implementation so the documented UI/API behavior matches the shipped workflow.

- [ ] Run the feasible checks for the touched UI code paths and record any limits if command execution remains unreliable in this environment.
