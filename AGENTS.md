# Crypto Taxes Project

## Introduction
This repository builds a local-first pipeline for ingesting crypto activity, transforming it into a consistent ledger/inventory model, and presenting the results in a UI for review and manual follow-up. The implemented domain model and current capabilities live in [doc/CURRENT.md](doc/CURRENT.md) (canonical) and [doc/WEALTH_MODEL.md](doc/WEALTH_MODEL.md) (supporting)
Treat other files under `doc/` as background/templates unless explicitly referenced.

## Repository layout
- `data/`: Python project (domain, ingestion/importers, transforms, tests, DB schema).
- `ui/`: Next.js app (presentation layer consuming the data API).
- `doc/`: canonical domain reference and supporting notes/templates.
- `artifacts/`: local-only inputs/outputs and caches (e.g., `accounts.json`, `seed_lots.csv`, transaction caches).

## Working conventions
- When working in `data/` or `ui/`, read and follow the nearest component `AGENTS.md` ([data/AGENTS.md](data/AGENTS.md), [ui/AGENTS.md](ui/AGENTS.md), and any deeper scoped ones) for the authoritative commands and coding guidelines.
- When reading unfamiliar code, check for `README.md` in the current directory and then walk upward toward the repo root, reading any `README.md` files on that direct path for additional context.

## Component interface (data ↔ ui)
- Shared contract: FastAPI endpoints exposed by `data/src/api/`.
- Base URL is configured via `CRYPTO_TAXES_API_URL` (defaults to `http://localhost:8000` for local dev).
- Event endpoints: `GET /raw-events`, `GET /seed-events`, `GET /corrected-events`.

## Docs and drift control
- When changing domain semantics, ingestion behavior, DB schema, or UI expectations, update `doc/CURRENT.md` and any relevant `AGENTS.md` files to keep the “how to work here” guidance accurate.

## Secrets and local artifacts
- API keys/config live in `data/.env` (see `data/.env.example`); do not commit secrets.
- `artifacts/` and `crypto_taxes.db` are local outputs/inputs and are not committed.
