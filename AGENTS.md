# Repository Guidelines

## Development commands
- `make deps` syncs the project and `dev` dependency groups into the local `.venv` via uv.
- `make code_check` runs `ruff check`, `ruff format --check`, and `mypy` to gate linting and types.
- `make code_fix` executes `ruff check --fix`, `ruff format`, and `mypy` to auto-fix linting and re-run types.
- `make test` runs the pytest suite (`uv run --group dev pytest -s`).

### Running commands and scripts
- Use `uv run <command>` to execute project-aware tooling and Python scripts inside the managed virtualenv.
- Reserve `uv run --group dev …` for commands that depend on dev-only packages (pytest, ruff, mypy, etc.); regular application scripts (e.g., under `scripts/`) work with plain `uv run python path/to/script.py`.

## Suggested workflow
- ALWAYS after making code changes `make code_fix` to auto-apply lint fixes. Don't ask for permission, just run it.
- ALWAYS after making code changes run `make test` to ensure the suite passes before committing. Don't ask for permission, just run it.
- When changing domain logic/semantics, update `doc/CURRENT.md` to keep the domain reference in sync.

## Project docs map
- Current domain model: `doc/CURRENT.md`
- Notes/ideas: `doc/ideas.md`

Prefer the “Current” guide for domain semantics.

## Domain reference
- Domain semantics and data model are defined in `doc/CURRENT.md`.

## Implementation conventions
- Python 3.13; Pydantic v2 models under `src/domain`.
- Use `Decimal` for numeric quantities/rates; avoid floats.
- Time fields use `datetime` named `timestamp` and are stored in UTC.
  - Convert inbound times to UTC at ingestion boundaries so internal models are always UTC.
- IDs: entities expose `id: UUID`. References use `<entity>_id: UUID` (e.g., `acquired_leg_id`).
- Keep comments/docstrings lean: only retain them when they convey non-obvious intent or context. Remove and avoid boilerplate comments that simply restate what the code already says.
- Avoid defensive programming inside the system: assume in-process data and types already satisfy invariants, and only perform validation/repairs at ingestion boundaries. When docs guarantee an invariant (e.g., timestamps already in UTC), do not re-normalize or re-validate it within domain/services code.

## Domain modules
- Ledger and lots: `src/domain/ledger.py`
- Inventory engine + lot matching: `src/domain/inventory.py`
- Pricing snapshots (crypto and fiat unified): `src/domain/pricing.py`

## Price services
- `src/services/price_service.py`, `price_store.py`, `price_sources.py` implement the caching layer used by the domain `PriceProvider`.

## Example tests
- Simple ETH trade flow: `tests/domain_eth_trades_test.py`

## Legacy implementation (to be updated)
- `src/db/*` (persistence models and usage)
- `src/main.py`
- `src/reports.py`

These modules reflect an older implementation and are not yet aligned with the current domain models under `src/domain`. Prefer building new logic against the domain layer. If you must modify legacy code, keep changes minimal and note any semantic differences in `doc/CURRENT.md`.
