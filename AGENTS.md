# Repository Guidelines

## Development commands
- `make deps` syncs the project and `dev` dependency groups into the local `.venv` via uv.
- `make code_check` runs `ruff check`, `ruff format --check`, and `mypy` to gate linting and types.
- `make code_fix` executes `ruff check --fix`, `ruff format`, and `mypy` to auto-fix linting and re-run types.
- `make test` runs the pytest suite (`uv run --group dev pytest -s`).

## Suggested workflow
- After making code changes run `make code_fix` to auto-apply lint fixes.
- Follow up with `make test` to ensure the suite passes before committing.
- When changing domain logic/semantics, update `doc/CURRENT.md` to keep the domain reference in sync.

## Project docs map
- Current domain model: `doc/CURRENT.md`
- Target architecture (future): `doc/FUTURE.md`
- Notes/ideas: `doc/ideas.md`

Prefer the “Current” guide for domain semantics. Use the “Future” guide for architectural direction and roadmap decisions.

## Domain reference
- Domain semantics and data model are defined in `doc/CURRENT.md`.

## Implementation conventions
- Python 3.13; Pydantic v2 models under `src/domain`.
- Use `Decimal` for numeric quantities/rates; avoid floats.
- Time fields use `datetime` named `timestamp` and are stored in UTC.
  - Convert inbound times to UTC at ingestion boundaries so internal models are always UTC.
- IDs: entities expose `id: UUID`. References use `<entity>_id: UUID` (e.g., `acquired_leg_id`).

## Domain modules
- Ledger and lots: `src/domain/ledger.py`
- Pricing snapshots (crypto and fiat unified): `src/domain/pricing.py`

## Example tests
- Simple ETH trade flow: `tests/domain_eth_trades_test.py`

## Legacy implementation (to be updated)
- `src/db/*` (persistence models and usage)
- `src/kraken_importer.py`
- `src/main.py`
- `src/reports.py`

These modules reflect an older implementation and are not yet aligned with the current domain models under `src/domain`. Prefer building new logic against the domain layer. If you must modify legacy code, keep changes minimal and note any semantic differences in `doc/CURRENT.md`.
