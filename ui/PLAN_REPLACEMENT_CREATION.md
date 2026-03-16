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
- expose exchange-owned leg accounts through `/accounts` so the replacement editor can offer all valid account choices

This plan is primarily UI-focused, but it includes a small backend `/accounts` change because the replacement editor cannot offer complete account choices unless exchange-owned system accounts are exposed through the API.

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
- `/accounts` currently returns records derived from `AccountRegistry.from_path()`, which means accounts coming only from importer constants such as Coinbase and Kraken are absent unless duplicated in `artifacts/accounts.json`.
- The unused `owned_accounts` set in `data/src/main.py` does not solve the frontend problem because it is not shared with the API and currently sits on an unreachable path after the early `return`.
- Exchange-owned accounts should become part of `AccountRegistry` itself so the backend has one canonical account catalog for both configured wallets and built-in system accounts.

## Scope Decisions

- Use a structured modal editor for the first pass.
- Keep creation and deletion in the same page-level action flow managed by `Events.tsx`.
- Fix spam-selection eligibility as part of this task instead of leaving the current unsafe behavior in place.
- Do not implement replacement editing in place.
- Do not add special corrected-lane affordances beyond removing invalid selection controls from synthetic events.
- For initial editor defaults:
  - prefill the replacement timestamp with the latest timestamp among the selected source events
  - allow the operator to edit both date and time manually before saving, with the editor operating in UTC
  - prefill the replacement leg draft from all selected source-event legs
  - sort the initial leg draft by currency and then by account name
  - still require the operator to review and edit the authoritative replacement payload before saving

## Design Outline

### Selection model

#### Selection identity and storage

- Keep selection keyed by raw-event identity using `eventOriginKey(eventOrigin)`.
- Keep the mutable selection state simple as `Set<string>` of selected origin keys.
- Do not introduce a persistent selection catalog that duplicates event payloads already present in `eventsByTimestamp`.

#### Selection eligibility and UI affordance

- Build selectable eligibility as `ReadonlySet<string>` of origin keys derived from the currently loaded lane items.
- Treat selectable cards as cards that still represent raw imported events:
  - all `raw-event` items in the raw lane
  - `corrected-event` items in the corrected lane only when they still carry a non-`INTERNAL` raw `EventOrigin`
- If the same raw-backed event is visible in both the raw lane and the corrected lane, both cards map to the same origin-key selection and should behave as one selected source.
- Treat non-selectable items as:
  - all correction lane items
  - corrected synthetic seed events
  - corrected synthetic replacement events
- Only render a checkbox for selectable items so the UI no longer implies invalid actions are supported.

#### Action-time source resolution

- When an action needs concrete source-event data, resolve it on demand from `eventsByTimestamp` using the selected origin-key set instead of storing duplicated event payloads in selection state.
- Add a helper that returns the selected source events with:
  - `eventOrigin`
  - source `timestamp`
  - source `legs`
- Spam actions should consume only the resolved `eventOrigin` values.
- Replacement creation should consume the resolved `eventOrigin`, `timestamp`, and `legs` values for draft prefilling.

### Replacement editor

- Add a dedicated client component under `ui/src/components/Events/` for replacement creation.
- The editor should show:
  - selected source origins as read-only metadata
  - authoritative replacement timestamp input with manual UTC date/time editing
  - repeatable leg rows with `assetId`, `accountChainId`, `quantity`, `isFee`
  - add/remove leg controls
  - client-side validation for missing timestamp, empty legs, zero/blank quantities, and blank required fields
- Build the initial timestamp draft from the latest selected source-event timestamp before the operator makes manual UTC edits.
- Keep timestamp display, editing, and API submission aligned to UTC to avoid browser-local timezone drift.
- Build the initial leg rows by flattening all selected source-event legs and sorting them by `assetId` and then resolved account display name before the draft is shown.
- Keep the payload editor structured; do not expose free-form JSON.

### Accounts data

- The editor needs the full account list for the account selector, not just display-name lookup.
- Extend `AccountRegistry` so it always merges:
  - configured on-chain account records from `accounts.json`
  - built-in system exchange accounts such as Coinbase and Kraken
- Do not rely on `owned_accounts` in `data/src/main.py` as the source of truth for the API surface.
- Prefer a lightweight shared system-account definition module instead of importing importer modules into `accounts.py`, so future exchanges such as Binance can be added in one place.
- Treat built-in exchange accounts as a separate input model from `AccountConfig`; do not represent them as fake address-based wallet config entries.
- Use a unified API-visible account record model that can represent both:
  - address-backed wallet accounts
  - built-in system exchange accounts without inventing fake addresses
- Keep `AccountRegistry.resolve_owned_id(...)` focused on address-backed wallet resolution while `records()` and `name_for(...)` operate on the merged catalog.
- Load the merged account list on the server and expose it through a client context/provider near the existing account names provider.

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

- Changing selection helpers and eligibility rules will touch multiple layers: selection hook, action bar, date section, lane item, and event card rendering.
- `router.refresh()` can invalidate the current selection state; success handlers should clear local selection first to avoid stale UI state during refresh.
- Timestamp editing must remain UTC end to end; using browser-local date/time controls without explicit UTC handling would introduce drift.
- The replacement editor must not rely on preserving leg order or source order beyond what the backend currently guarantees.
- Client-side validation should stay lightweight and defer rule enforcement about raw/spam/replacement overlap to the backend.
- The merged `/accounts` list must avoid duplicate `account_chain_id` entries if a future configuration path overlaps with a built-in system account.
- The merged registry should also reject configured account names that conflict with reserved built-in system account names.

## Open Questions

- None currently. The modal-based first pass and set-based selection plus action-time source resolution approach are assumed for implementation unless the operator changes direction.

## Steps

- [x] Introduce a dedicated replacement-creation plan reference in the broader UI plan if needed so active tracking is not split ambiguously.

- [x] Keep selection state in `ui/src/components/Events/` as `Set<string>` of origin keys and refactor selection helpers to expose selectable origin-key sets instead of event payload maps.

- [x] Tighten selectable eligibility so only raw-backed cards render mutation checkboxes, while synthetic corrected events and all correction-lane items never do.

- [x] Add an action-time resolver for selected source events so spam and replacement flows can obtain `eventOrigin`, `timestamp`, and `legs` from `eventsByTimestamp` only when needed.

- [x] Update the spam action flow to consume the set-based selection model while preserving current behavior for valid raw-backed events.

- [x] Refactor `AccountRegistry` so it merges configured wallet accounts with built-in system exchange accounts.

- [x] Introduce the minimal supporting account models/shared definitions needed for system exchange accounts without overloading `AccountConfig` with fake wallet data.

- [x] Add conflict validation for duplicate merged account IDs and configured names that collide with reserved built-in system account names.

- [x] Keep `/accounts` backed by `AccountRegistry` records so the API automatically exposes the merged catalog.

- [x] Add or update backend coverage for `/accounts` so exchange-owned accounts remain exposed to the UI.

- [x] Add client-side accounts context/data plumbing so replacement forms can render account selectors from the merged server-loaded accounts dataset.

- [x] Extend replacement correction API helpers and shared UI types to support create payloads and structured API error handling.

- [x] Implement a replacement editor modal with source summary, timestamp input, repeatable leg rows, and lightweight client-side validation.

- [x] Add the `Replace selected` action to the action bar and wire it to open the editor from the current selection.

- [x] Implement replacement create submission, conflict/error feedback, success feedback, selection reset, and `router.refresh()` after successful create.

- [x] Update existing delete success paths for spam and replacement corrections to use `router.refresh()` so the corrections lane reflects removals immediately.

- [x] Update `ui/README.md`, `doc/CURRENT.md`, `data/README.md`, and `AGENTS.md` after implementation so the documented UI/API behavior matches the shipped workflow.

- [x] Run the feasible checks for the touched UI code paths and record any limits if command execution remains unreliable in this environment.
