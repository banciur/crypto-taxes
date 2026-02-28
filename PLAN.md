# Plan File Guide

This file is a persistent planning document used across multiple sessions.
It is both documentation for the current task and a tracking tool for progress.
This section is generic guidance for AI and should remain stable across tasks unless the planning format itself is intentionally changed.
During task discussion and implementation, update the task-specific sections below so they always reflect the current understanding of the work.

- Keep completed work marked with `[x]` so the historical record is preserved.
- Keep remaining work marked with `[ ]` until it is actually finished.
- Continue implementation from the first unchecked item unless the task scope is intentionally reordered.
- Update the task-specific sections when decisions change, so this file stays current.
- Add new steps below the existing ones instead of rewriting history.

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

- [ ] Implement automatic Moralis spam detection persistence during import.
  Notes:
  - During `MoralisImporter.load_events`, inspect fetched Moralis transactions for the upstream spam flag and persist matching entries into `spam_corrections`.
  - Use persistent rows in the corrections DB and call `mark_as_spam(..., skip_if_exists=True)` so manual removals are not overwritten by future imports.
  - Exact placement inside the importer flow is agreed broadly, but small code-structure details are still being decided.

- [ ] Add backend support for a mixed corrections feed.
  Notes:
  - The current corrections lane is seed-only; it must evolve to return both seed events and spam correction entries.
  - Spam correction entries should include enough data for the UI to place them on the correct day and show the unique event identifier.
  - Raw event details should not be duplicated into the corrections lane response.
  - Exact API response shape is still being decided.

- [ ] Update the UI to render multiple correction item types.
  Notes:
  - Keep the raw lane unchanged visually except for an action to mark an event as spam.
  - Keep the corrected lane sourced only from `corrected_ledger_events`.
  - Replace the current seed-only corrections lane rendering with components that can display both seed events and spam correction entries.
  - Spam correction entries should support removing the spam marker.
  - The component structure and final interaction details are still being decided.

- [ ] Validate the end-to-end spam correction workflow.
  Notes:
  - Verify auto-detected Moralis spam markers are persisted.
  - Verify manual mark/unmark flows persist correctly.
  - Verify the corrections lane shows seed events and spam correction entries as intended.
  - Verify the corrected lane reflects changes after the manual rerun workflow.

- [ ] Decide how corrected-data synchronization should work long term.
  Notes:
  - This decision is intentionally deferred to the end of the task.
  - Current accepted workflow: after marking or unmarking spam, rerun the full pipeline and rerun the UI.
  - Future improvement to decide later: whether corrected data should be rebuilt automatically after spam edits.
