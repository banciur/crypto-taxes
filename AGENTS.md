# Crypto Taxes Project

## Introduction
This repository builds a local-first pipeline for ingesting crypto activity, transforming it into a consistent ledger/inventory model, and presenting the results in a UI for review and manual follow-up. The implemented domain model and current capabilities live in [doc/CURRENT.md](doc/CURRENT.md) (canonical) and [doc/WEALTH_MODEL.md](doc/WEALTH_MODEL.md) (supporting)
Treat other files under `doc/` as background/templates unless explicitly referenced.

## Repository layout
- `data/`: Python project (domain, API, ingestion/importers, transforms, tests, DB schema).
- `ui/`: Next.js app (presentation layer consuming the data API).
- `doc/`: canonical domain reference and supporting notes/templates.
- `artifacts/`: local-only inputs/outputs and caches (e.g., `accounts.json`, `seed_lots.csv`, transaction caches).

## Required context lookup
- As soon as it is clear a task touches `data/` or `ui/`, read the matching component guide as the first step: [data/README.md](data/README.md) for `data/` work and [ui/README.md](ui/README.md) for `ui/` work.
- When reading or editing a specific file, also check that file's directory and each parent directory up to the component root for `README.md` files, and read any that exist for additional local context.
- Example: before changing `data/src/importers/moralis/moralis_importer.py`, read `data/README.md`, then check `data/src/importers/moralis/README.md`, `data/src/importers/README.md`, and `data/src/README.md`.

## Component interface (data ↔ ui)
- Shared contract: FastAPI endpoints exposed by `data/src/api/`.
- Base URL is configured via `CRYPTO_TAXES_API_URL` (defaults to `http://localhost:8000` for local dev).

## Docs and drift control
- When changing domain semantics, ingestion behavior, DB schema, API contracts, or UI expectations, update `doc/CURRENT.md`, this `AGENTS.md`, and any relevant `README.md` files immediately so the documented guidance stays in sync with the current implementation.

## Secrets and local artifacts
- API keys/config live in `data/.env` (see `data/.env.example`); do not commit secrets.
- `artifacts/` are local outputs/inputs and are not committed.
- Coinbase Track imports currently persist raw rows in `artifacts/transactions_cache.db`. Treat Coinbase as one consolidated account and prefer full-snapshot sync over per-wallet incremental logic unless explicitly told otherwise.
