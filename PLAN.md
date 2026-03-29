# Plan File Guide

This file is a persistent planning document used across multiple sessions.
It is both documentation for the current task and a tracking tool for progress.
This section is generic guidance for AI and should remain stable across tasks unless the planning format itself is intentionally changed.
When creating a task-specific plan from this template, keep the full guide section intact so future sessions can still see the operating rules.

This file has two phases:

**Planning phase** — before any implementation begins. The agent's role is to actively help prepare the plan by asking all necessary questions upfront, challenging vague requirements, and ensuring every step is unambiguous before execution starts. All open questions should be surfaced and resolved in this phase, not during implementation. The phase ends when the operator explicitly confirms the plan is ready for execution.

**Execution phase** — once the plan is confirmed. The agent switches to a focused executor role:
- Implement steps one by one. After each completed step, stop and let the operator validate before continuing.
- Steps should be very precise and specific. Decisions belong in the planning phase, not here.
- If anything is unclear or ambiguous, stop and ask the operator. Do not make assumptions.
- Only do what is explicitly described in the steps. Do not add improvements or fixes that are not mentioned.
- While executing, act as a senior developer — improve code quality as you go: refactor, remove duplication, simplify complexity, improve naming, apply better patterns, and leave code cleaner than you found it.
- Keep completed work marked with `[x]` so the historical record is preserved.
- Keep remaining work marked with `[ ]` until it is actually finished.
- Update the task-specific sections immediately when understanding changes; do not batch updates.


## Current Task

Design and later implement the first UI surface for backend wallet tracking.

Intended outcome:
- Load the existing `GET /wallet-tracking` backend state into the Next.js app.
- Present wallet-tracking status, progress markers, balances, and blocking issues in the UI.
- Keep the implementation read-only; no rebuild or mutation controls in this task.
- Integrate the wallet-tracking view into the current layout without forcing the snapshot data into the timeline lane model.

Current planning status:
- Draft plan prepared.
- Awaiting operator feedback on the remaining UI shape decisions before execution starts.

Working assumptions for the draft:
- Wallet tracking should be shown as a dedicated summary panel, not as another timeline lane.
- The panel should be rendered in the main content area above the existing timeline/action-bar stack.
- The first version should always be visible when the page loads; no separate toggle or route is required.
- The first version should remain read-only and should only consume the current API response.

## Open Questions

- Should the wallet-tracking panel always be visible above the timeline, or do you want it hidden behind an explicit toggle/accordion?
- For balances, is a flat table (`account`, `asset`, `balance`) enough for the first version, or do you want account-grouped sections immediately?
- On `FAILED`, should balances remain fully expanded by default, or should the issues section be expanded first with balances collapsed?

Recommended defaults if not overridden:
- Always visible panel above the timeline.
- Flat balances table for the first version.
- On `FAILED`, show both summary and issues first, with balances still visible below.

## Scope

In scope:
- Shared UI API module and TypeScript types for wallet tracking.
- Server-side page loading of wallet-tracking data.
- Read-only wallet-tracking panel/components.
- Rendering of `NOT_RUN`, `COMPLETED`, and `FAILED` states.
- UI tests if the repo already has a suitable pattern, otherwise rely on type/lint coverage for this first pass.
- Documentation updates only if the UI contract/behavior meaningfully changes during implementation.

Out of scope:
- Triggering rebuilds from the UI.
- Polling or live refresh.
- Timeline-lane integration for wallet tracking.
- Advanced filtering, sorting, pagination, CSV export, or per-wallet drill-down flows.
- Any backend changes unless implementation exposes a concrete contract gap.

## Proposed UI Design

Recommended placement:
- Render a `WalletTrackingPanel` in the right/main column above `Events`.
- Keep the left toolbar focused on column/date controls; wallet tracking is a global snapshot, not a lane/date filter.

Reasoning:
- The current UI’s lane model is timestamp-bucket based.
- Wallet tracking is a single snapshot over corrected events, not a feed of timestamped items.
- Forcing it into `COLUMN_DEFINITIONS`, `EventsByTimestamp`, and `TimestampBucketRow` would distort the current model and add avoidable complexity.

Recommended panel structure:

1. Summary header
- Title: `Wallet tracking`
- Status badge: `Not run`, `Completed`, or `Failed`
- Small explanatory copy tied to the status
- On all states, show `processed_event_count`

2. Marker section
- `last_applied_event` if present
- `failed_event` if present
- Render each marker as `location / external_id`

3. Blocking issues section
- Only render for `FAILED`
- One row/card per issue
- Show:
  - account name (via `AccountNamesContext`)
  - asset id
  - attempted delta
  - available balance
  - missing balance
  - event origin reference

4. Final balances section
- Render for `COMPLETED` and `FAILED`
- Flat table with columns:
  - account
  - asset
  - balance
- Reuse account-name resolution from `AccountNamesContext`
- Keep decimal values string-backed and format with shared decimal helpers

5. Empty-state messaging
- `NOT_RUN`: explain that no wallet-tracking snapshot has been persisted yet
- Mention that correction changes still require the backend pipeline rerun before corrected outputs and wallet tracking refresh

## Technical Design

Recommended new UI API module:
- `ui/src/api/walletTracking.ts`

Recommended new UI types:
- `ui/src/types/walletTracking.ts`

Recommended shapes:

```ts
type WalletTrackingStatus = "NOT_RUN" | "COMPLETED" | "FAILED";

type WalletTrackingBalance = {
  accountChainId: string;
  assetId: string;
  balance: DecimalString;
};

type WalletTrackingIssue = {
  event: EventOrigin;
  accountChainId: string;
  assetId: string;
  attemptedDelta: DecimalString;
  availableBalance: DecimalString;
  missingBalance: DecimalString;
};

type WalletTrackingState = {
  status: WalletTrackingStatus;
  processedEventCount: number;
  lastAppliedEvent?: EventOrigin | null;
  failedEvent?: EventOrigin | null;
  issues: WalletTrackingIssue[];
  balances: WalletTrackingBalance[];
};
```

Recommended component modules:
- `ui/src/components/WalletTracking/WalletTrackingPanel.tsx`
- `ui/src/components/WalletTracking/WalletTrackingIssueList.tsx`
- `ui/src/components/WalletTracking/WalletTrackingBalancesTable.tsx`

Component responsibilities:
- `WalletTrackingPanel`
  - top-level status/layout component
  - chooses which sections render for each status
- `WalletTrackingIssueList`
  - formats the failed-event issue rows
- `WalletTrackingBalancesTable`
  - renders the balances list with account name resolution

Integration point:
- `ui/src/app/page.tsx`

Recommended loading flow:
- fetch `accounts`
- fetch `walletTracking`
- fetch selected timeline columns
- pass `walletTracking` into the main content tree alongside `eventsByTimestamp`

Recommended rendering flow:
- keep `Events` responsible for correction actions and timeline rendering
- wrap `Events` with a small page-level stack:
  - `WalletTrackingPanel`
  - `Events`

## Testing / Validation Plan

If implementation proceeds as proposed, validate with:
- `pnpm prettier`
- `pnpm lint`
- `pnpm types`

Recommended test coverage during execution:
- API module returns the typed wallet-tracking payload.
- `NOT_RUN` renders the empty-state copy.
- `COMPLETED` renders balances and processed count.
- `FAILED` renders issues, failed marker, and retained balances.
- Account IDs resolve to display names in balances/issues where available.

## Steps

- [ ] Add `ui/src/types/walletTracking.ts` and `ui/src/api/walletTracking.ts` for the read-only `GET /wallet-tracking` contract, keeping decimal fields string-backed and camelCase at the TypeScript boundary.

- [ ] Load wallet-tracking state in `ui/src/app/page.tsx` alongside accounts and selected columns, and thread it into the main content tree without routing it through the timestamp-bucket lane model.

- [ ] Add wallet-tracking UI components under `ui/src/components/WalletTracking/` to render the summary header, event markers, failed issues, and balances table using shared account-name and decimal-format helpers.

- [ ] Integrate the `WalletTrackingPanel` above the existing timeline/action-bar stack so wallet tracking is visible as a global snapshot while corrections/events continue to use the current lane UI unchanged.

- [ ] Add or adjust UI tests if a lightweight pattern exists for these components; otherwise validate through `pnpm prettier`, `pnpm lint`, and `pnpm types`, and document any testing gap explicitly in the execution summary.
