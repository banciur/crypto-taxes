# Plan File Guide

This file is a persistent planning document used across multiple sessions.
It is both documentation for the current task and a tracking tool for progress.
This section is generic guidance for AI and should remain stable across tasks unless the planning format itself is intentionally changed.
When creating a task-specific plan from this template, keep the full guide section intact so future sessions can still see the operating rules.

This file has two phases:

**Planning phase** — before any implementation begins. The agent's role is to actively help prepare the plan by asking all necessary questions upfront, challenging vague requirements, and ensuring every step is unambiguous before execution starts. All open questions should be surfaced and resolved in this phase, not during implementation. The resulting plan should read as an execution contract, not a brainstorming record. The phase ends when the operator explicitly confirms the plan is ready for execution.

Apply each decision across the whole document before moving on: replace the terms it renames, remove the claims it invalidates, adjust the steps whose scope or order it changes, and update the open questions it answers, splits, or raises. A consequence stated in one section must also reach the step that implements it. Report what changed, or that nothing did, so the operator can see the decision's reach. A decision is recorded only once the document is consistent with it.

**Execution phase** — once the plan is confirmed. The agent switches to a focused executor role:
- Implement steps one by one. After each completed step, stop and let the operator validate before continuing.
- Steps should be very precise and specific. Decisions belong in the planning phase, not here.
- If anything is unclear or ambiguous, stop and ask the operator. Do not make assumptions.
- Only implement the behavior explicitly described in the steps. Do not add new features or behavior changes that are not part of the plan.
- While executing, act as a senior developer — improve the quality of the code you touch: refactor, remove duplication, simplify complexity, improve naming, apply better patterns, and leave code cleaner than you found it.
- Such refactoring is allowed, but it must never be silent: explicitly mention any improvement you make when reporting the completed step, so the operator can review it.
- Keep completed work marked with `[x]` so the historical record is preserved.
- Keep remaining work marked with `[ ]` until it is actually finished.
- Update the task-specific sections immediately when understanding changes; do not batch updates.

## Plan Content Rules

Task-specific plan sections must describe only the implementation target and the work required to reach it.

Use positive, executable statements:
- Prefer "Add `X` after `Y`"
- Avoid things like "Do not add a CLI flag."
- Avoid "No rollout mode is planned."
- Avoid documenting speculative alternatives once a decision is made.

Resolved decisions must be folded into the relevant task, flow, requirements, or steps. Do not keep a decision log unless the operator explicitly asks for one.

Keep open questions separate from implementation requirements. Remove each open question once answered and update the concrete plan text accordingly.

Do not add non-features, future possibilities, rejected options, or defensive "do not do X" instructions unless they are necessary to prevent a likely destructive or incorrect implementation.

Plan steps should be complete work units:
- Each step should produce a coherent, reviewable change.
- Each step should be small enough to implement and validate independently.
- Each step should be suitable for a separate commit when practical.
- A step may span code, tests, cleanup, and documentation when those changes are required to complete one logical work item.
- Avoid steps that mix unrelated behavior changes in one item.

## Current Task

Add German tax computation as a `TAX_COMPUTATION` stage running after the acquisition/disposal projection.

The stage is a pure function over data the pipeline already persists: acquisition lots, disposal links, and corrected ledger events. It produces one record set, `TaxEvent`.

### Record shape

```
TaxEvent
  source_id         -> disposal_links.id | acquisition_lots.id; run-scoped join key
  event_origin      \
  account_chain_id   |  EventLegRef, exposed as source_leg_ref
  asset_id           |
  is_fee            /
  kind              -> PRIVATE_SALE (§23) | OTHER_INCOME (§22)
  occurred_at       -> disposal date, or receipt date
  amount_eur        -> signed gain for §23, receipt value for §22
```

For a `PRIVATE_SALE`, `amount_eur` is `disposal.proceeds_total - disposal.quantity_used * lot.cost_per_unit`. For an `OTHER_INCOME` it is `lot.quantity_acquired * lot.cost_per_unit`.

`kind` names the German tax category. `doc/TAXES.md` owns what each value means, which movements land under it, and the legal questions still open; the enum's docstring states each value's paragraph and what `amount_eur` means for it.

The table holds only tax-relevant rows: a `PRIVATE_SALE` per disposal link inside the §23 speculation period, an `OTHER_INCOME` per acquisition lot whose source event was a one-sided receipt. A disposal held beyond the period produces no row and stays in `disposal_links`, which the inspection step reads to confirm nothing was dropped.

Everything else a reader wants — quantity, proceeds, cost basis, acquisition date, the lot that funded a disposal — is one join away through `source_id`, so the API composes it rather than the schema freezing it.

`amount_eur` is the row's contribution to its category's taxable base, signed — a §23 loss is negative, while an `OTHER_INCOME` row is always positive. Totals are aggregated per kind, since §23 and §22 are separate baskets.

`EventLegRef` is the stable anchor: the handle the UI correlates against the events lane, and a tx hash a human can paste into a block explorer. All three parts of `leg_key` are load-bearing, because a residual can split across accounts into separate lots and a fee leg coexists with a non-fee leg of the same asset. It is deliberately not unique per row: a disposal leg funded by three lots yields three rows sharing one anchor, since the period test applies per fragment. `source_id` is what distinguishes them.

`AbstractAcquisitionDisposal` already carries these flat fields with a `source_leg_ref` property; `TaxEvent` mirrors that rather than inventing a key.

### Acquisition classification

An acquisition lot produces an `OTHER_INCOME` row when its source corrected event was a one-sided receipt, decided by `is_income_receipt(event) -> bool`:

```
non-fee legs -> net per asset -> flip sign for liability assets
  every surviving net positive -> receipt
  otherwise                    -> not a receipt, no row
```

This is a pure function of the corrected event and static asset configuration. It needs no prices: the only asset whose EUR value opposes its quantity sign is a liability token, and that is a config lookup. A `+10000 GHO` / `+10000 variableDebtEthGHO` borrow is therefore not a receipt.

Fiat legs count as counterparts like any other asset, so a `-5000 EUR` / `+268 ETH` purchase is not a receipt. A fiat-only event such as a bare EUR deposit reads as one, which is never consulted because fiat opens no FIFO lot.

Classification lives in the tax layer; acquisition lots carry no tax classification field. The predicate answers a shape question and the stage assigns the paragraph.

### Identity

`tax_events` lives in the main DB, which `run()` recreates with `reset=True` on every run alongside the projection it derives from. `source_id` is therefore a plain UUID join key, valid for exactly as long as the row it points at exists, matching how `DisposalLink.lot_id` already works. Durable identity is `EventLegRef`, which is what anything outside a single run refers to.

## Steps

- [ ] **Tax model and persistence.** Rewrite `src/domain/tax_event.py` around a single `TaxEvent` with the fields listed above, a `source_leg_ref` property returning `EventLegRef`, and `TaxEventKind` (`PRIVATE_SALE`, `OTHER_INCOME`) whose docstring states each value's paragraph and what `amount_eur` means for it. Rewrite `src/db/tax_events.py` to match: the `tax_events` table gains the leg-anchor columns, `kind` becomes the tax category, and the repository exposes `replace()` and `get()` following `db/acquisition_disposal.py`. Add the `EventOrigin` column helper to `db/mixins.py` and use it here. Update the tax-event cases in `tests/db/repositories_test.py`.

- [ ] **Classification.** Add `src/domain/assets.py` with `is_liability_asset(asset_id)`, matching the union of `ASSETS_PRICED_AS_NEGATED` values against the uppercased asset id so mixed-case ledger ids match. Add `AbstractEvent.net_non_fee_quantities() -> dict[AssetId, Decimal]` to `src/domain/ledger.py`, returning the net quantity per asset across non-fee legs with zero-net assets dropped, and rewire `project_event_quantities` to source nets from it so both callers net identically; `_project_asset_group` then takes the net as an argument and always returns a group. Add `src/domain/tax_classification.py` holding `is_income_receipt(event) -> bool` implementing the rule above. Test the classifier against a staking receipt, a `EUR -> ETH` purchase, an `ETH -> USDC` swap, a GHO borrow, a GHO repayment, a receipt whose only other leg is gas, and a bare EUR deposit; the purchase case is load-bearing, because excluding fiat before the counterpart test silently reclassifies every fiat purchase as income. Test `is_liability_asset` with a mixed-case id, and `net_non_fee_quantities` directly. The projection rewire carries no behavior change and is covered by the existing projection tests.

- [ ] **Wire the `TAX_COMPUTATION` stage.** Add the stage to `src/main.py` after the acquisition/disposal projection, wrapped in `_run_system_state_stage` so failures land in `SystemState` (the enum member already exists). The stage indexes corrected events by `event_origin`, emits an `OTHER_INCOME` `TaxEvent` for every acquisition lot whose source event is an income receipt, emits a `PRIVATE_SALE` `TaxEvent` for every disposal link falling inside the §23 speculation period, and persists them clear-then-write. The period is compared on Europe/Berlin calendar dates rather than timestamp differences: a disposal is inside it up to and including the anniversary of its lot's acquisition date, and outside it from the day after. Update `data/README.md` and `doc/CURRENT.md` for the new stage and its outputs, with `doc/CURRENT.md` summarising the stage and pointing at `doc/TAXES.md` the way it already points at `doc/LOT_MATCHING.md`. Cover the period boundary with tests: a disposal on the anniversary of its lot's acquisition date emits a row, one on the following day does not, and a lot funding several disposal fragments is tested per fragment.

- [ ] **Run and inspect.** Run `uv run src/main.py`, then query `tax_events` for: `PRIVATE_SALE` total and count per year, `OTHER_INCOME` total per year, and `OTHER_INCOME` rows sorted by `amount_eur` descending. Reconcile disposal counts and proceeds against `disposal_links`, so a disposal dropped through a bad lot match or a wrong timestamp shows up as a gap instead of silently vanishing from the taxable set. Record the findings in this file under a new section, including whether the classification holds up against the largest receipts.

- [ ] **Tax summary page.** Add a `/taxes` route showing taxable amounts folded by year, month and day. A year opens to its months and a month to its days. Each row carries the `PRIVATE_SALE` and `OTHER_INCOME` totals for its period in separate columns, since the two baskets never combine.

  Extract the year/month/day grouping from `ui/src/components/DateChooser.tsx` into a shared helper parameterised by the value it aggregates, and use it for both the chooser's counts and the summary's amounts. Keep the human-owned comment at the top of `DateChooser.tsx` intact.

  The year rows carry the figures that go on a return. For §23: net gains against losses within the private-sale basket, where losses offset only §23 gains, carry back one year, and carry forward indefinitely under §10d. Apply the §23 Freigrenze to the year's total gain — €600 through 2023, €1,000 from 2024 — free below the threshold and fully taxable at or above it. For §22: sum the receipts and apply the €256 Freigrenze the same way.

  Add the API endpoint behind it, returning the tax event amounts by day and kind plus the year-level figures. It computes them on read, since they are a fold over `tax_events` with no other input. Update `ui/README.md` for the new route and the shared grouping helper.
