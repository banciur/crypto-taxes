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

Redesign inventory processing so it produces a deterministic, ordered projection from corrected ledger events into `AcquisitionLot` and `DisposalLink` records without relying on transient leg UUIDs.

Current processing contract:

- `AbstractEvent` enforces per-event leg identity uniqueness.
- Per-event leg identity is represented as `LegKey(account_chain_id, asset_id, is_fee)`.
- Full trace-back to a source leg is represented as `EventLegRef(event_origin, leg_key)`.
- Duplicate leg identities are invalid system state and must raise during event model validation.
- Inventory processing assumes its input events are already sorted chronologically; it must not validate sort order.
- Processing output is limited to:
  - an ordered list of `AcquisitionLot`
  - an ordered list of `DisposalLink`
- `AcquisitionLot` and `DisposalLink` live in `src/domain/acquisition_disposal.py` as a separate projection layer, not in `ledger.py`.
- `AcquisitionLot` and `DisposalLink` are self-sufficient for downstream tax/presentation work and expose derived `leg_key` and `source_leg_ref` properties through a shared abstract base.
- `InventoryResult` exposes only ordered `acquisition_lots` and `disposal_links`. `open_inventory` has been removed from the public result.
- FIFO matching is maintained per asset, with one `DisposalLink` emitted per consumed lot slice.
- Internal transfer handling remains structural: same-asset, non-fee, non-EUR incoming/outgoing legs with equal totals are ignored by inventory matching.
- Compatibility fallout from the projection redesign has been carried through immediate downstream persistence/debug/tax helper code so the current test suite remains green.

Open decisions to resolve before execution:

- Whether lot/disposal IDs should remain random `uuid4` values or become deterministic IDs derived from their source identity.

## Steps

- [x] Finalize the new processing model shape for `AcquisitionLot` and `DisposalLink` in [acquisition_disposal.py](/Users/banciur/projects/crypto-taxes/data/src/domain/acquisition_disposal.py), replacing `*_leg_id` references with source event identity plus explicit leg identity fields and the quantities/timestamps needed so downstream code does not need to rejoin into ledger events.

- [x] Move leg identity validation into `AbstractEvent` in [ledger.py](/Users/banciur/projects/crypto-taxes/data/src/domain/ledger.py) so every event validates that no two legs share the same `(account_chain_id, asset_id, is_fee)` tuple, and define a clear validation error message because duplicate legs are invalid domain state.

- [x] Refactor the inventory engine in [inventory.py](/Users/banciur/projects/crypto-taxes/data/src/domain/inventory.py) to consume the new event invariant and emit the redesigned `AcquisitionLot` and `DisposalLink` models without any dependency on leg UUIDs.

- [x] Preserve the existing matching behavior where one disposal can consume multiple prior lots FIFO, still creating one `DisposalLink` per `(disposal leg identity, matched lot)` slice.

- [x] Keep the current classification rules in the processor unless they directly conflict with the new invariant:
  - positive non-EUR non-transfer legs create acquisition lots
  - negative non-EUR non-transfer legs consume lots
  - internal transfer legs do not create lots or disposals
  - fee semantics remain represented through `is_fee`

- [x] Define and implement the output ordering contract in [inventory.py](/Users/banciur/projects/crypto-taxes/data/src/domain/inventory.py) so returned `AcquisitionLot` and `DisposalLink` lists are explicitly sorted by timestamp and then stable identity tie-breakers.

- [x] Redesign or remove `InventoryResult` in [inventory.py](/Users/banciur/projects/crypto-taxes/data/src/domain/inventory.py) so the public processing result matches the agreed scope for this phase.

- [x] Update processing tests in [inventory_test.py](/Users/banciur/projects/crypto-taxes/data/tests/domain/inventory_test.py) to cover:
  - duplicate leg identity rejection at the event model level
  - acquisition creation with the new lot shape
  - disposal matching with the new disposal-link shape
  - one disposal consuming multiple lots
  - transfer handling
  - fee handling
  - deterministic output ordering

- [x] Update any now-broken downstream tests or helper code that still depend on leg-UUID-based inventory outputs. This included immediate persistence/debug/tax-summary compatibility so the current backend suite remains consistent with the new projection model.
