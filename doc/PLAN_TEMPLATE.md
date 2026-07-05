# Plan File Guide

This file is a persistent planning document used across multiple sessions.
It is both documentation for the current task and a tracking tool for progress.
This section is generic guidance for AI and should remain stable across tasks unless the planning format itself is intentionally changed.
When creating a task-specific plan from this template, keep the full guide section intact so future sessions can still see the operating rules.

This file has two phases:

**Planning phase** — before any implementation begins. The agent's role is to actively help prepare the plan by asking all necessary questions upfront, challenging vague requirements, and ensuring every step is unambiguous before execution starts. All open questions should be surfaced and resolved in this phase, not during implementation. The resulting plan should read as an execution contract, not a brainstorming record. The phase ends when the operator explicitly confirms the plan is ready for execution.

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

Describe the current task and the intended outcome here. Replace this section for each new task.

## Steps

- [x] Example completed step

- [ ] Example next step
