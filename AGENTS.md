# Repository Guidelines

## Coding conventions / best practices
- Keep comments/docstrings lean: only retain them when they convey non-obvious intent or context. Remove and avoid boilerplate comments that simply restate what the code already says.
- Avoid defensive programming inside the system: assume in-process data and types already satisfy invariants and only perform validation/repairs at ingestion boundaries. When docs/typings guarantee an invariant, do not re-normalize or re-validate it within domain/services code.
- Tests should derive expected values from the inputs defined in the test (shared variables/constants) instead of retyping literals in assertions to keep cases DRY and less brittle.
- Do not leave unused code or data "for future use"; remove unused pieces and avoid implementing speculative features.

## Development commands
- `make deps` syncs the project and `dev` dependency groups into the local `.venv` via uv.
- `make code_check` runs `ruff check`, `ruff format --check`, and `mypy` to gate linting and types.
- `make code_fix` executes `ruff check --fix`, `ruff format`, and `mypy` to auto-fix linting and re-run types.
- `make test` runs the pytest suite. If you want to test a single file use `uv run --group dev pytest -s tests/test_foo.py` 

### Running commands and scripts with uv
- Use `uv run <command or path to python file>` to execute project-aware tooling and Python scripts inside the managed virtualenv;
- Add `--group dev` ex. `uv run --group dev <command or path to python file>` for operations that depend on dev packages (pytest, ruff, mypy, etc.);
- Examples:
  - `uv run src/main.py` for running the main entrypoint;
  - `uv run --group dev pytest -s tests/domain/inventory_test.py` for running the test file;

## Suggested workflow
- ALWAYS after making code changes `make code_fix` to auto-apply lint fixes. Don't ask for permission, just run it.
- ALWAYS after making code changes run `make test` to ensure the suite passes before committing. Don't ask for permission, just run it.
- When changing domain logic/semantics, update `doc/CURRENT.md` to keep the domain reference in sync.

## Directory structure
- `src/`: Python application code and domain modules.
- `tests/`: pytest suite.
- `doc/`: domain reference (`CURRENT.md` is source of truth).
- `frontend/`: Next.js app providing the UI for the project.
- `scripts/`: helper scripts.
- `data/`: project data artifacts (e.g., seeds, fixtures).

## Project Practices
- Python 3.13; Pydantic v2 models under `src/domain`; Tests written in `pytest` under `tests`.
- Use `str` for identifiers (e.g., `asset_id: str`) and `UUID` for UUIDs (e.g., `asset_id: UUID`). Avoid `int` for identifiers.
- Use `Decimal` for numeric quantities/rates; avoid floats.
- Time fields use `datetime` named `timestamp` and are stored in UTC.
  - Convert inbound times to UTC at ingestion boundaries so internal models are always UTC.
- IDs: entities expose `id: UUID`. References use `<entity>_id: UUID` (e.g., `acquired_leg_id`).

## Domain reference
- Domain semantics and data model are defined in `doc/CURRENT.md`.
- Ignore other files from the `doc` directory except for `CURRENT.md` and `WEALTH_MODEL.md`.

## Domain modules
- Ledger and lots: `src/domain/ledger.py`
- Inventory engine and lot matching: `src/domain/inventory.py`
- Pricing snapshots (crypto and fiat unified): `src/domain/pricing.py`

## Price services
- `src/services/price_service.py`, `price_store.py`, `price_sources.py` implement the caching layer used by the domain `PriceProvider`.

