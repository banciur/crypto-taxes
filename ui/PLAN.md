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

Add checkbox selection to cards in the `Corrected events` lane so users can mark events for spam correction even when the raw lane is hidden. Raw and corrected cards that represent the same logical event must share one selection state keyed by `eventOrigin`, so selecting either card immediately updates the other and the action bar counts that event only once. The middle `Corrections` lane remains unchanged and non-selectable.

## Steps

- [x] Review the current UI implementation for lane rendering, event selection, and spam marker actions.

- [x] Confirm task scope and selection behavior: only the `Corrected events` lane gets new checkboxes, and raw/corrected cards share one origin-based selection.

- [x] Create this persistent task plan in `ui/PLAN.md` from `doc/PLAN_TEMPLATE.md`.

- [x] Refactor the event selection state in `ui/src/components/Events/Events.tsx` from raw-specific naming to shared event-selection naming while keeping `eventOriginKey(eventOrigin)` as the canonical identity.

- [x] Rename raw-specific selection props and callbacks in `ui/src/components/VirtualizedDateSections.tsx`, `ui/src/components/EventDateSection.tsx`, and `ui/src/components/LaneItem.tsx` to generic event-selection naming.

- [x] Derive the full selectable event dataset from loaded `raw-event` and `corrected-event` items in `eventsByTimestamp`, and use that dataset both to resolve selected `EventOrigin` values for spam creation and to prune stale selections when loaded selectable items change.

- [ ] Render checkbox controls for both `raw-event` and `corrected-event` cards through `ui/src/components/EventCard.tsx`, and update checkbox labels to refer to `event` rather than `raw event`.

- [ ] Keep mirrored selection behavior across lanes: if raw and corrected cards share the same `eventOriginKey`, toggling either one updates both immediately and the action bar count changes once.

- [ ] Update `ui/src/components/EventsActionBar.tsx` so it is shown when at least one selectable lane is loaded (`raw` or `corrected`) and so its status text is generic to selected events rather than raw events.

- [ ] Confirm the `Corrections` lane remains unchanged: `seed-correction` and `spam-correction` items stay non-selectable and preserve their current behavior.

- [ ] Verify the flow with `pnpm lint` and `pnpm types` in `ui`, plus a manual UI check covering corrected-only selection, shared raw/corrected selection, and column-toggle behavior.
