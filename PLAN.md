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

Design and later implement backend-only wallet tracking for corrected ledger data.

Intended outcome:
- Consume corrected `LedgerEvent` objects in processing order.
- Build the current wallet-balance state only; no historical run retention.
- Stop before the first blocking wallet-balance failure and persist the partial result plus error details.
- Expose the current state through FastAPI so the UI can display processing status, last processed marker, final balances, and any blocking error.
- Keep UI implementation out of scope.

Current planning status:
- Draft plan prepared.
- Planning questions resolved by the operator on 2026-03-26.
- Ready for operator sign-off before execution starts.

Confirmed decisions:
- Processing input starts as `Iterable[LedgerEvent]`.
- The caller is responsible for providing corrected events, not raw events.
- Wallet tracking is a separate projection from lot generation and tax computation.
- Track all assets, including fiat like `EUR`.
- Store all blocking balance issues from the first failed event.
- `GET /wallet-tracking` returns `NOT_RUN` instead of `404` when no state exists yet.
- Only the current wallet-tracking state is stored in SQLite.
- Per-event deltas are not persisted.
- Snapshot recomputation remains part of backend processing; no API-triggered rebuild is included in this task.
- Repository and service names should not imply historical versions.
- Remove `data/src/domain/wallet_balance_tracker.py` as part of the implementation and move all remaining callers to the new wallet-tracking projection design.
- When corrected events are loaded from persistence for wallet tracking, use canonical deterministic order: `timestamp`, `event_origin.location`, `event_origin.external_id`.
- For this task, integrate wallet-tracking rebuild immediately before the current `return  # just for now` in `data/src/main.py` and do not execute any later inventory/tax work.
- `processed_event_count` counts only fully applied events.
- `failed_event` is the first event whose wallet-tracking processing fails.
- A rebuild with zero corrected events still persists a `COMPLETED` state with `processed_event_count = 0`; `NOT_RUN` is reserved for "no state has been persisted yet".

Challenge to current assumption:
- Same-timestamp event order can change wallet-tracking results, so persistence and service layers should still load corrected events in canonical deterministic order:
  - `timestamp`
  - `event_origin.location`
  - `event_origin.external_id`

## Open Questions

None currently.

Planning-phase decisions already confirmed:
- track all assets
- store all blocking issues from the first failed event
- return `NOT_RUN` from the API when no state exists yet

## Scope

In scope:
- Domain models and projector for wallet tracking.
- SQLite persistence for the current wallet-tracking state.
- Pipeline/service integration that rebuilds the state from corrected events.
- Read-only API endpoint for the current state.
- Tests and documentation updates for the backend/API contract.

Out of scope:
- Lot generation or tax computation changes.
- Automatic transfer inference.
- Wallet-tracking history across multiple runs.
- UI React components or pages.
- API-triggered recomputation.

## Target Design

The wallet tracker becomes a dedicated projection with three layers:

1. Pure projection layer
- Accept corrected `LedgerEvent` objects in deterministic order.
- Aggregate each event into net per-wallet deltas.
- Validate the whole event atomically.
- Return a completed or failed state object instead of raising a business exception for insufficient balances.

2. Persistence layer
- Store only the current state in the main SQLite DB.
- Replace the current state transactionally on each rebuild.
- Store final balances and blocking issues for the first failed event.

3. API layer
- Expose a single read endpoint returning the current state or a `NOT_RUN` placeholder.
- Keep decimal values string-backed at the API boundary.

## Domain Objects

Recommended new module:
- `data/src/domain/wallet_tracking.py`

Recommended shapes:

```python
from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic_base import StrictBaseModel

from domain.ledger import AccountChainId, AssetId, EventOrigin, LedgerEvent


class WalletTrackingStatus(StrEnum):
    NOT_RUN = "NOT_RUN"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class WalletBalance(StrictBaseModel):
    account_chain_id: AccountChainId
    asset_id: AssetId
    balance: Decimal


class WalletTrackingIssue(StrictBaseModel):
    event: EventOrigin
    account_chain_id: AccountChainId
    asset_id: AssetId
    attempted_delta: Decimal
    available_balance: Decimal
    missing_balance: Decimal


class WalletTrackingState(StrictBaseModel):
    status: WalletTrackingStatus
    processed_event_count: int
    last_applied_event: EventOrigin | None = None
    failed_event: EventOrigin | None = None
    issues: list[WalletTrackingIssue]
    balances: list[WalletBalance]
```

Notes:
- `balances` should contain only non-zero balances.
- `issues` should be empty for `COMPLETED` and `NOT_RUN`.
- `failed_event` should equal the event referenced by every issue in a failed state.

## Projector Interface

Recommended class:

```python
class WalletProjector:
    def project(self, events: Iterable[LedgerEvent]) -> WalletTrackingState:
        ...
```

Recommended behavior:
- Net each event into `dict[tuple[AccountChainId, AssetId], Decimal]`.
- Ignore zero net deltas after event-level aggregation.
- Validate all resulting balances for the event before mutating state.
- If validation succeeds, apply all deltas and advance `last_applied_event`.
- If validation fails, do not apply any delta from the failed event.
- Return a `FAILED` state with balances from the last fully applied event and the blocking issue list for the failed event.
- Do not depend on `PriceProvider`, lot state, or tax logic.

Recommended internal helpers:

```python
class WalletProjector:
    def project(self, events: Iterable[LedgerEvent]) -> WalletTrackingState: ...
    def _net_event_deltas(
        self, event: LedgerEvent
    ) -> dict[tuple[AccountChainId, AssetId], Decimal]: ...
    def _validate_event(
        self,
        event: LedgerEvent,
        deltas: dict[tuple[AccountChainId, AssetId], Decimal],
        balances: dict[tuple[AccountChainId, AssetId], Decimal],
    ) -> list[WalletTrackingIssue]: ...
```

## Persistence Design

Recommended new module:
- `data/src/db/wallet_tracking.py`

Recommended tables:

1. `wallet_tracking_state`
- exactly one row when state exists; empty table means `NOT_RUN`
- `status: str`
- `processed_event_count: int`
- `last_applied_origin_location: str | None`
- `last_applied_origin_external_id: str | None`
- `failed_origin_location: str | None`
- `failed_origin_external_id: str | None`

2. `wallet_tracking_balances`
- `account_chain_id: str`
- `asset_id: str`
- `balance: Decimal`
- primary key or unique constraint on `(account_chain_id, asset_id)`

3. `wallet_tracking_issues`
- `position: int`
- `event_origin_location: str`
- `event_origin_external_id: str`
- `account_chain_id: str`
- `asset_id: str`
- `attempted_delta: Decimal`
- `available_balance: Decimal`
- `missing_balance: Decimal`
- primary key or unique constraint on `position`

Repository interface:

```python
class WalletTrackingRepository:
    def get(self) -> WalletTrackingState | None: ...
    def replace(self, state: WalletTrackingState) -> WalletTrackingState: ...
```

Repository behavior:
- `replace` must delete all existing wallet-tracking rows and insert the new state in one transaction.
- `get` returns the only stored state or `None`.
- Balances are returned sorted deterministically by `account_chain_id`, `asset_id`.
- Any persistence-layer read path that supplies corrected events for projection must preserve canonical deterministic order:
  - `timestamp`
  - `origin_location`
  - `origin_external_id`

Reason for no foreign-key state id on child tables:
- The design stores only one current state, never multiple versions.
- `wallet_tracking_balances` and `wallet_tracking_issues` are current-state tables, not versioned child rows.
- The repository replaces all three tables in one transaction, so referential versioning is not needed.

## Pipeline Integration

Recommended rebuild flow:
- Load corrected events from persistence.
- Sort them in canonical deterministic order: `timestamp`, `event_origin.location`, `event_origin.external_id`.
- Project the state with `WalletProjector`.
- Save it with `WalletTrackingRepository.replace()`.
- Any read path that needs API-facing `NOT_RUN` semantics should synthesize that in-memory when `WalletTrackingRepository.get()` returns `None`.

Pipeline integration point:
- After corrected events are persisted in `data/src/main.py`, rebuild the wallet-tracking state from corrected events immediately before the current `return  # just for now`.
- Do not process raw events.
- Do not couple wallet tracking to `InventoryEngine`.
- Do not execute any inventory, disposal, tax, or summary work after the wallet-tracking rebuild in this task.

Required cleanup as part of this task:
- Remove `data/src/domain/wallet_balance_tracker.py`.
- Remove wallet-balance concerns from [inventory.py](/Users/banciur/projects/crypto-taxes/data/src/domain/inventory.py).
- Update any remaining callers, tests, fixtures, or helpers that still import the old wallet-balance tracker.

## API Contract

Recommended new router:
- `data/src/api/wallet_tracking.py`

Recommended endpoint:
- `GET /wallet-tracking`

Recommended response model:

```python
class WalletTrackingState(StrictBaseModel):
    status: WalletTrackingStatus
    processed_event_count: int
    last_applied_event: EventOrigin | None
    failed_event: EventOrigin | None
    issues: list[WalletTrackingIssue]
    balances: list[WalletBalance]
```

Recommended response semantics:
- `NOT_RUN`
  - `processed_event_count = 0`
  - `last_applied_event = null`
  - `failed_event = null`
  - `issues = []`
  - `balances = []`
- `COMPLETED`
  - `failed_event = null`
  - `issues = []`
  - `processed_event_count` equals the number of fully applied events and may be `0`
- `FAILED`
  - `processed_event_count` equals the number of fully applied events before the failure
  - `last_applied_event` points to the last fully committed event
  - `failed_event` points to the first blocking event
  - `issues` contains all blocking balance issues for that event
  - `balances` reflect state as of `last_applied_event`

FastAPI integration:
- Add dependency provider in `data/src/api/dependencies/__init__.py`
- Include the router from `data/src/api/api.py`

No write endpoints in this task:
- No `POST /wallet-tracking/rebuild`
- No mutation routes

Reason:
- The existing workflow already treats corrected pipeline outputs as manually rebuilt.
- Read-only API is enough for the first UI integration.

## Test Plan

New test files:
- `data/tests/domain/wallet_tracking_test.py`
- `data/tests/db/wallet_tracking_repository_test.py`
- `data/tests/api/wallet_tracking_api_test.py`

Domain projector cases:
- successful processing across multiple events and accounts
- event-level same-key netting before validation
- event-atomic failure leaves failed-event deltas unapplied
- failed state includes last-applied marker and failed-event marker
- failed state includes all blocking issues from the first failed event
- balances exclude zero rows
- fiat tracking behavior according to the confirmed asset-scope decision

Repository cases:
- `get` returns `None` when empty
- `replace` persists completed state
- `replace` replaces prior failed/completed state fully
- `replace` persists multiple balances and multiple issues deterministically

API cases:
- empty storage returns `NOT_RUN`
- persisted completed state is returned unchanged
- persisted failed state returns balances, failed marker, and issues
- decimal fields remain string-backed in the JSON response

Integration case:
- pipeline rebuild after corrected-event persistence stores the wallet-tracking state based on corrected events, not raw events
- pipeline rebuild runs before the current early `return` in `data/src/main.py`, and no later inventory/tax work executes in this task

## Documentation Updates Required During Execution

Update these files in the same implementation change:
- `data/README.md`
- `data/src/api/README.md`
- `doc/CURRENT.md`
- `AGENTS.md`
- `ui/README.md`

Required doc changes:
- describe wallet tracking as a separate corrected-ledger projection
- document current-state persistence semantics
- document stop-on-first-error partial-state behavior
- document the `GET /wallet-tracking` API contract
- note that UI rendering is still separate from backend/API delivery

## Steps

- [x] Add `data/src/domain/wallet_tracking.py` with `WalletTrackingStatus`, `WalletBalance`, `WalletTrackingIssue`, `WalletTrackingState`, and `WalletProjector`; implement event-atomic wallet projection in `WalletProjector.project(events: Iterable[LedgerEvent]) -> WalletTrackingState`, including per-event delta netting, first-failure stop behavior, non-zero balance capture, and issue collection for the failed event; and add domain tests in `data/tests/domain/wallet_tracking_test.py` covering happy path, same-event netting, partial failure semantics, multi-issue failed event, and zero-balance exclusion.

- [x] Add persistence in `data/src/db/wallet_tracking.py` with ORM models for current state, balances, and issues plus `WalletTrackingRepository.get()` and `WalletTrackingRepository.replace()`, and add repository tests in `data/tests/db/wallet_tracking_repository_test.py` covering empty state, state replacement, deterministic ordering, and failed-state issue persistence.

- [x] Integrate wallet-tracking rebuild into the corrected-events processing flow in `data/src/main.py` by loading corrected events, sorting them canonically, projecting with `WalletProjector`, and persisting with `WalletTrackingRepository` immediately after corrected events are persisted and immediately before the current `return  # just for now`, without executing any later inventory/tax work.

- [x] Add `data/src/api/wallet_tracking.py`, add the dependency factory in `data/src/api/dependencies/__init__.py`, include the router in `data/src/api/api.py`, and expose `GET /wallet-tracking` with the agreed `NOT_RUN`/`COMPLETED`/`FAILED` response semantics.

- [ ] Add API tests in `data/tests/api/wallet_tracking_api_test.py` covering empty-state, completed state, failed state, and decimal serialization behavior.

- [ ] Remove `data/src/domain/wallet_balance_tracker.py` and update or remove any remaining imports/usages in production code and tests so wallet tracking exists only in the new projection module.

- [ ] Update `data/README.md`, `data/src/api/README.md`, `doc/CURRENT.md`, `AGENTS.md`, and `ui/README.md` so the documented backend and API behavior matches the implemented wallet-tracking projection exactly.
