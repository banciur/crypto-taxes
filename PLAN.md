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
- After each implemented step, update any affected docs and relevant local guidance files so they stay aligned with the current implementation.

## Current Task

Finish the spam corrections implementation so the system can persist Moralis-detected spam, expose spam corrections in the UI as part of the corrections lane, support manual spam mark and unmark actions, and document the current manual synchronization workflow.

## Steps

- [x] Define the initial plan structure in `PLAN.md` and document how future sessions should use it.
  Notes: This establishes the baseline workflow and tracking format for all follow-up work.

- [x] Align the broad product scope for spam corrections before implementation details.
  Notes: Agreed behavior:
  - Raw lane stays unchanged and shows raw events only.
  - Manual spam marking is triggered from the raw lane.
  - Corrections lane becomes a mixed lane and should include seed events plus lightweight spam correction entries.
  - Spam correction entries in the corrections lane should not show raw event details, only correction information and the unique identifier.
  - Removing a spam marker is triggered from the spam correction entry in the corrections lane.
  - Corrected lane stays unchanged and shows only `corrected_ledger_events`.
  - The UI does not need to display the spam marker source.
  - For now, synchronization after manual spam edits is manual: rerun the full pipeline and rerun the UI.

- [x] Implement automatic Moralis spam detection persistence during import.
  Notes:
  - During `MoralisImporter.load_events`, inspect fetched Moralis transactions for the upstream `possible_spam` flag and persist matching entries into `spam_corrections`.
  - Persist a spam marker only when the transaction is marked as spam and successfully produces a `LedgerEvent`.
  - Use `mark_as_spam(..., skip_if_exists=True)` so manual removals are not overwritten by future imports.
  - Inject `SpamCorrectionRepository` into `MoralisImporter` so the importer remains easy to test.
  - Keep the repository injection optional on the importer constructor so direct unit tests can still instantiate the importer in isolation; the runtime path passes the shared corrections repo from `data/src/main.py`.
  - Add importer-focused tests that cover spam marker creation, non-spam transactions, and preservation of manual overrides.
  - Completed: `data/src/main.py` now passes the shared corrections repo into the Moralis importer, and importer tests cover auto-marker creation plus manual tombstone preservation.

- [x] Extend existing correction APIs for the corrections lane.
  Notes:
  - Keep using the existing `/seed-events` endpoint for seed events.
  - Extend the existing `/spam-corrections` endpoint so it returns all data needed by the corrections lane.
  - Keep `SpamCorrectionRepository` focused on the corrections DB and enrich the `/spam-corrections` response in the API layer.
  - Expand `LedgerEventRepository` with a bulk lookup method that accepts multiple event origins and returns `Iterable[tuple[EventOrigin, datetime]]` for the matching raw-event timestamps.
  - Spam correction entries should include the correction record id, the marked event origin, and the exact raw-event timestamp in the same format as the original event.
  - Raw event details should not be duplicated into the spam-corrections response.
  - Ordering of spam correction entries should follow the same chronological behavior as raw events so it is easy to compare what was marked.
  - If a spam marker cannot be matched to exactly one raw event while building the API response, code should fail loudly because the data is inconsistent.
  - Completed: `GET /spam-corrections` now enriches corrections with raw-event timestamps in chronological order, `LedgerEventRepository` exposes a bulk origin-to-timestamp lookup, and API tests cover timestamp enrichment plus orphan-marker failure handling.

- [x] Enforce raw-event origin uniqueness in the main events database.
  Notes:
  - Add a DB-level uniqueness constraint for `ledger_events` on (`origin_location`, `origin_external_id`) so the API invariant is guaranteed by storage, not just importer behavior.
  - Add a repository-level test that duplicate raw-event origins fail to persist.
  - Update docs to reflect that raw events are now structurally unique by `EventOrigin`.
  - Completed: `ledger_events` now has a unique constraint on raw event origin, repository tests assert duplicate origins fail, and the multiple-match API test was removed because new schemas cannot persist that state.

- [x] Update the UI to render multiple correction item types.
  Notes:
  - Refactor the current UI rendering pipeline so the lane renderer is no longer tied to a single `EventCard` shape.
  - Keep the day-and-column layout, but switch to rendering a typed list of lane items through a type-based renderer.
  - Build a shared correction-item parent component that provides the common layout and styling for correction entries, with specific seed and spam components rendering their own inner content.
  - The corrections lane should render from a combined list of UI objects and switch rendering based on the correction item type.
  - Keep the raw lane visually unchanged except for per-event selection checkboxes.
  - Support selecting one or more raw events, then use a sticky top action area with a `Mark as spam` button to submit the selected events in one action.
  - Keep the existing mark API shape and send one `POST /spam-corrections` request per selected event, in parallel, when performing the bulk mark action.
  - Do not attempt rollback for partial failures; send all requests, show success only if all succeed, and if any fail show failure and print the request errors to the console for manual follow-up.
  - Keep the corrected lane sourced only from `corrected_ledger_events`.
  - Replace the current seed-only corrections lane rendering with components that can display both seed events and spam correction entries using the same general visual pattern but different labels.
  - Spam correction entries should expose a direct CTA to remove a single spam marker using a red X icon.
  - After mark/unmark actions, perform the API call, show a spinner while the request is in flight, and show success or failure feedback.
  - Do not reshuffle lane contents locally after actions; the manual rerun workflow remains the source of synchronization.
  - Completed: the UI now renders typed lane items through dedicated correction components, the raw lane supports multi-select spam marking, spam markers can be removed inline from the corrections lane, and the client shows in-flight plus success/failure feedback without locally reshuffling data.

- [x] Split UI backend communication into resource-specific API modules.
  Notes:
  - Keep reusable transport in `ui/src/api/core.ts`.
  - Move endpoint-specific backend communication into focused `ui/src/api/*` files instead of one mixed events module.
  - Start by separating account and spam-correction communication so non-event resources no longer live in `ui/src/api/events.ts`.
  - Completed: accounts and spam-correction communication now live in `ui/src/api/accounts.ts` and `ui/src/api/spamCorrections.ts`, shared API types/helpers were extracted, `ui/src/api/events.ts` now only handles event endpoints, and UI imports were updated without changing behavior.

- [x] Move UI account-name caching into a shared server helper.
  Notes:
  - Keep backend communication in `ui/src/api/accounts.ts`.
  - Add a shared helper in `ui/src/lib/accounts.ts` for cached account loading and account-name lookup reuse.
  - Remove the module-local account cache from `ui/src/consts.server.ts` and make server loaders consume the shared helper instead.
  - Completed: `ui/src/lib/accounts.ts` now owns the cached account lookup built on top of `getAccounts()` using a simple React `cache` wrapper, and `ui/src/consts.server.ts` reuses that shared helper instead of maintaining its own module-local promise.
