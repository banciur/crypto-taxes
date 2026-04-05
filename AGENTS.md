# Crypto Taxes Project

## Introduction

This repository builds a local-first pipeline for ingesting crypto activity, transforming it into a consistent ledger/inventory model, and presenting the results in a UI for review and manual follow-up. 

## Repository layout

- `data/`: Python project (domain, API, ingestion/importers, transforms, tests, DB schema).
- `ui/`: Next.js app (presentation layer consuming the data API).
- `doc/`: canonical domain reference and supporting notes/templates.
- `artifacts/`: local-only inputs/outputs and caches (e.g., `accounts.json`, correction/main DB files, transaction caches). **NEVER** commit files from this directory.

## Component interface (data ↔ ui)

- Shared contract: FastAPI endpoints exposed by `data/src/api/`.
- Base URL is configured via `CRYPTO_TAXES_API_URL` (defaults to `http://localhost:8000` for local dev).

## Secrets and configuration

- Secrets, API keys and general configuration live in `data/.env` (see `data/.env.example`). **NEVER** commit this file. 

## Documentation hierarchy
- `AGENTS.md` is the top-level map. Keep it limited to repo-wide structure, document ownership, and rules for how to find further guidance. Do not add feature-specific behavior here unless it is truly cross-cutting and important at the repository level.
- `doc/CURRENT.md` is the canonical description of the currently implemented business/domain behavior and cross-cutting system capabilities.
- `README.md` files are the authoritative source for component-level and directory-level implementation details, constraints, and workflows. The closer a `README.md` is to the code being changed, the more specific and authoritative it is for that area.
- Avoid duplicating the same guidance across levels. Higher-level docs should summarize and point downward; detailed rules should live in the lowest-level document that owns them.

## Required context lookup

- Read `doc/CURRENT.md` first for most tasks. Skip it only when the task is narrowly technical and cannot affect behavior, domain semantics, API contracts, or documented workflows.
- As soon as it is clear a task touches `data/` or `ui/`, read the matching component guide next: `data/README.md` for `data/` work and `ui/README.md` for `ui/` work.
- When reading or editing a specific file, also check that file's directory and each parent directory up to the component root for `README.md` files, and read any that exist for additional local context.
- Example: before reading or changing `data/src/importers/moralis/moralis_importer.py`, read `doc/CURRENT.md`, then `data/README.md`, then check `data/src/importers/moralis/README.md`, `data/src/importers/README.md`, and `data/src/README.md`.

## Docs and drift control

- Keep documentation hierarchical. Do not update `AGENTS.md`, `doc/CURRENT.md`, and local `README.md` files by default for every change.
- Update the lowest-level authoritative document that owns the changed behavior or guidance.
- Update `AGENTS.md` only when repository structure, documentation ownership, or repo-wide rules change.
- Update `doc/CURRENT.md` when the implemented business logic, domain semantics, cross-component behavior, or broadly relevant capabilities change.
- Update the relevant `README.md` files when component-specific or directory-specific behavior, technical constraints, workflows, or implementation details change.
- If a change is purely local, keep the update local. Propagate documentation upward only when the higher-level summary or contract has actually changed.
- When multiple documentation levels must change, avoid restating the same detail in each file; keep the detail in the most specific owning document and have higher-level docs reference it briefly.
