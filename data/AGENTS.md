# Data Guidelines

## Tech stack
- Python 3.13;
- Uses `uv` to manage dependencies and virtual environments;
- Pydantic v2 models under `src/domain`;
- Tests written in `pytest` under `tests`.

## Directory structure
- `src/`: Python application code and domain modules.
- `tests/`: pytest suite.
- `scripts/`: helper scripts.

## Domain modules
- Ledger and lots: `src/domain/ledger.py`
- Inventory engine and lot matching: `src/domain/inventory.py`
- Pricing snapshots (crypto and fiat unified): `src/domain/pricing.py`

## Price services
- `src/services/price_service.py`, `price_store.py`, `price_sources.py` implement the caching layer used by the domain `PriceProvider`.

## Data importers
- Importers live in `src/importers/` and translate upstream data sources into domain `LedgerEvent`s with normalized types (`Decimal`, UTC `timestamp`), canonical asset identifiers, and consistent `origin`/`ingestion` metadata.
- Current importers:
  - Kraken CSV ledger: `src/importers/kraken/kraken_importer.py`
  - on-chain trancations through Moralis service (ERC20-only currently): `src/importers/moralis/moralis_importer.py` 
  - Seed CSV events (for missing history): `src/importers/seed_events.py` loads synthetic acquisition events from `artifacts/seed_lots.csv` by default.

### Running commands and scripts with uv
- Use `uv run <command or path to python file>` to execute project-aware tooling and Python scripts inside the managed virtualenv;
- Add `--group dev` ex. `uv run --group dev <command or path to python file>` for operations that depend on dev packages (pytest, ruff, mypy, etc.);
- Examples:
  - `uv run src/main.py` for running the main entrypoint;
  - `uv run --group dev pytest -s tests/domain/inventory_test.py` for running the test file;

## Development commands
- `make deps` syncs the project and `dev` dependency groups into the local `.venv` via uv.
- `make code_check` runs `ruff check`, `ruff format --check`, and `mypy` to gate linting and types.
- `make code_fix` executes `ruff check --fix`, `ruff format`, and `mypy` to auto-fix linting and re-run types.
- `make test` runs the pytest suite. If you want to test a single file use `uv run --group dev pytest -s tests/test_foo.py`

## Suggested workflow
- ALWAYS after making python code changes `make code_fix` to auto-apply lint fixes.
- ALWAYS after making python code changes run `make test` to ensure the suite passes before committing.

## Project Practices
- Use `str` for identifiers (e.g., `asset_id: str`) and `UUID` for UUIDs (e.g., `asset_id: UUID`). Avoid `int` for identifiers.
- Use `Decimal` for numeric quantities/rates; avoid floats.
- Time fields use `datetime` named `timestamp` and are stored in UTC.
  - Convert inbound times to UTC at ingestion boundaries so internal models are always UTC.
- IDs: entities expose `id: UUID`. References use `<entity>_id: UUID` (e.g., `acquired_leg_id`).
