# Data Guidelines

## Capabilities and Structure

### Directory structure
- `src/`: Python application code and domain modules.
- `src/api/`: FastAPI service layer that exposes the backend contract consumed by the UI.
- `tests/`: pytest suite.
- `scripts/`: helper scripts.

### API
- The API is implemented with FastAPI under `src/api/`.
- Its purpose is to provide the UI with the backend data it needs and the allowed mutation capabilities for reviewing and modifying system state through a stable HTTP interface.

### Domain modules
- Ledger events: `src/domain/ledger.py`
- Acquisition/disposal projection models: `src/domain/acquisition_disposal.py`
- Acquisition/disposal projector and FIFO lot matching: `src/domain/acquisition_disposal_projection.py`
- Pricing snapshots (crypto and fiat unified): `src/domain/pricing.py`
- Unified correction model (`LedgerCorrection` for discard, replacement, and opening balance): `src/domain/correction.py`
- Tax event projection types: `src/domain/tax_event.py`
- Wallet tracking projection and statuses: `src/domain/wallet_projection.py`

### Correction persistence and application
- Unified correction persistence lives in `src/db/ledger_corrections.py`.
- One-off migration from legacy spam/replacement/seed tables lives in `scripts/migrate_ledger_corrections.py`; it backfills missing legacy rows into `ledger_corrections`, skips already-covered spam sources, and migrates legacy seed/opening-balance rows from the main DB.
- Ingestion-layer correction application and validation live under `src/corrections/`.
- Source-backed corrections occupy sources only while active. Deleting one hard-deletes the correction and records source-level auto-suppression so importer automation does not recreate it while manual recreation remains allowed.
- Current ingestion correction flow is: validate unified source ownership, remove all claimed raw events, emit synthetic events for corrections with legs, then sort corrected events once before persistence by `timestamp`, `event_origin.location`, and `event_origin.external_id`.

### Wallet tracking
- Wallet tracking is rebuilt from persisted corrected events.
- The rebuild stores only the current snapshot in database.
- A successful rebuild persists `COMPLETED`, including the zero-event case.
- A failed rebuild stops on the first blocking event and persists:
  - the failed event marker
  - all blocking balance issues for that failed event
  - balances as of the event immediately before the failed event

### Price services
- `src/services/price_service.py`, `price_store.py`, `price_sources.py` implement the caching layer used by the domain `PriceProvider`.

### Data importers
- Importers live in `src/importers/` and translate upstream data sources into domain `LedgerEvent`s with normalized types (`Decimal`, UTC `timestamp`), canonical asset identifiers, and consistent `event_origin`/`ingestion` metadata.
- Current importers:
  - Coinbase Track account history: `src/importers/coinbase/coinbase_importer.py`
  - Kraken CSV ledger: `src/importers/kraken/kraken_importer.py`
  - Stakewise reward CSV exports: `src/importers/stakewise/stakewise_importer.py`
  - Lido reward CSV exports: `src/importers/lido/lido_importer.py`
  - on-chain transactions through Moralis importer: `src/importers/moralis/moralis_importer.py`
- Moralis and Coinbase persist raw upstream data in the SQLite cache DB at `artifacts/transactions_cache.db` to reduce API calls during syncs.

## Technical Workflow

### Tech stack
- Python 3.13;
- Uses `uv` to manage dependencies and virtual environments;
- Pydantic v2 models under `src/domain`;
- Tests written in `pytest` under `tests`.

### Running commands and scripts with uv
- Run data commands from `data/` (`cd data`).
- Use `uv run <command or path to python file>` to execute project-aware tooling and Python scripts inside the managed virtualenv;
- Add `--group dev` ex. `uv run --group dev <command or path to python file>` for operations that depend on dev packages (pytest, ruff, mypy, etc.);
- Examples:
  - `uv run src/main.py` for running the main entrypoint;
  - `uv run --group dev pytest -s tests/domain/acquisition_disposal_projection_test.py` for running the test file;

### Development commands
- Run these commands from `data/`.
- `make deps` syncs the project and `dev` dependency groups into the local `.venv` via uv.
- `make dev` starts the FastAPI app with auto-reload for local development.
- `make code_check` runs `ruff check`, `ruff format --check`, and `mypy` to gate linting and types.
- `make code_fix` executes `ruff check --fix`, `ruff format`, and `mypy` to auto-fix linting and re-run types.
- `make test` runs the pytest suite. If you want to test a single file, use `uv run --group dev pytest tests/test_foo.py`

### Suggested workflow
- **ALWAYS** after making python code changes `make code_fix` to auto-apply lint fixes.
- **ALWAYS** after making python code changes run `make test` to ensure the suite passes before committing.

### Project practices
- Use `str` for identifiers (e.g., `asset_id: str`) and `UUID` for UUIDs (e.g., `asset_id: UUID`). Avoid `int` for identifiers.
- Use `Decimal` for numeric quantities/rates; avoid floats.
- Time fields use `datetime` named `timestamp` and are stored in UTC.
  - Convert inbound times to UTC at ingestion boundaries so internal models are always UTC.
- Some ORM tables may include DB-only audit fields such as `created_at` and `updated_at`. Keep them out of domain and API models unless they are intentionally part of the exposed contract.
- `EventOrigin` (`origin_location` + `origin_external_id`) is the stable unique identifier of a raw ledger event. Design event identity and cross-event references around it.
- Do not design event relationships around transient event UUIDs or leg UUIDs. Those are internal identifiers that may change across re-imports or rebuilds.
- `AbstractEvent` enforces that event legs are unique by `(account_chain_id, asset_id, is_fee)`. Treat duplicates as invalid domain input rather than silently merging them.
- IDs: entities expose `id: UUID`. Keep cross-layer references based on stable domain identity such as `EventOrigin` and canonical leg identity fields instead of transient event or leg UUIDs.
- `AccountRegistry` is the canonical merged account catalog. Keep address-backed wallet resolution (`resolve_owned_id`) separate from built-in system exchange accounts, which are selectable in the UI but do not participate in wallet-address ownership lookup. System account IDs are location-derived (`COINBASE:coinbase`, `KRAKEN:kraken`), so location/address can be recovered from `account_chain_id`.
