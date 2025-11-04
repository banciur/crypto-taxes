# crypto-taxes
Yet another unfinished system for tracking crypto transactions and calculating taxes. But I need something tailored for a stable farmer in Germany.

## Docs
- Current domain model: `doc/CURRENT.md`
- Target architecture and roadmap: `doc/FUTURE.md`
- Developer/agent workflow: `AGENTS.md`

## Quickstart
Project uses [uv](https://docs.astral.sh/uv/) with Python 3.13.

- Setup: `make deps`
- Run tests: `make test`
- Code quality: `make code_fix` (autofix) or `make code_check` (lint+types)

## Repo Layout
- `src/domain` — Pydantic v2 domain models (ledger, lots, pricing)
- `src/db`, `src/kraken_importer.py`, `src/main.py`, `src/reports.py` — legacy modules (to be modernized)
- `tests` — pytest suite (domain example: `tests/domain_eth_trades_test.py`)
- `doc` — `CURRENT.md` (now), `FUTURE.md` (roadmap), `ideas.md`
