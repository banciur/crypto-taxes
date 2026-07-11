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
- Acquisition/disposal projection models and projector package: `src/domain/acquisition_disposal/`
- Target lot-matching model and rationale: `../doc/LOT_MATCHING.md`
- Pricing snapshots (crypto and fiat unified): `src/domain/pricing.py`
- Unified correction model (`LedgerCorrection` for discard, replacement, and opening balance): `src/domain/correction.py`
- Main-flow run status: `src/domain/system_state.py`
- Tax event projection types: `src/domain/tax_event.py`
- Wallet balance projection: `src/domain/wallet_projection.py`

### Main-flow system state
- The main pipeline persists the latest `SystemState` in `src/db/system_state.py`.
- Active stages currently written by `src/main.py` are `RAW_IMPORT`, `CORRECTIONS`, `WALLET_PROJECTION`, and `ACQUISITION_DISPOSAL`.
- Stage execution writes `RUNNING` before work starts. Successful completion after the acquisition/disposal projection writes `COMPLETED`.
- Failures write `FAILED` with a flat `SystemStateError` (`exception_type`, `message`, optional `traceback`). Exceptions record the exception class name, its message, and traceback.
- Every stage, including wallet projection, fails the same way: it raises a domain exception that the stage wrapper records as `FAILED`. There is no per-stage failure status field.

### Correction persistence and application
- Unified correction persistence lives in `src/db/ledger_corrections.py`.
- Ingestion-layer correction application and validation live under `src/corrections/`.
- Source-backed corrections occupy sources only while active. Deleting one hard-deletes the correction and records source-level auto-suppression so importer automation does not recreate it while manual recreation remains allowed.
- Current ingestion correction flow is: validate unified source ownership, remove all claimed raw events, emit synthetic events for corrections with legs, then sort corrected events once before persistence by `timestamp`, `event_origin.location`, and `event_origin.external_id`.

### Wallet balances
- Wallet balances are rebuilt from persisted corrected events into the `wallet_balances` table via `WalletBalanceRepository` (clear-then-write); only the current snapshot is stored.
- `WalletProjector` folds corrected events into per-`(account, asset)` balances. It raises `WalletProjectionError` (carrying the failing event and every blocking balance issue) on the first event that would drive a balance negative.
- On failure the wallet stage persists balances as of the last fully applied event before re-raising, so the partial (and possibly incoherent) snapshot is visible for debugging. Run health, including the failed stage and error, lives only in `SystemState`; the `/wallet-balances` endpoint returns bare balances with no status.

### Acquisition/disposal projection
- After a successful wallet projection, the main flow rebuilds the acquisition/disposal projection from the same shared corrected-events list.
- `AcquisitionDisposalProjector` (`src/domain/acquisition_disposal/`) values events and matches disposals against open lots via FIFO, producing `AcquisitionLot`s and `DisposalLink`s.
- The projection is persisted with clear-then-write semantics through `AcquisitionDisposalProjectionRepository.replace()`, replacing any previous projection.
- The stage first loads the stored price overrides and calls `validate_overrides` against the corrected events, so a stale override fails `ACQUISITION_DISPOSAL` rather than escaping the stage wrapper. Validation lives here and not in `CORRECTIONS` because overrides do not affect the corrected-event stream, and failing earlier would also block the wallet projection the operator needs while fixing the override.
- Projector failures (e.g. not-enough-open-lots, unavailable required prices) propagate as exceptions and are recorded as a `FAILED` `SystemState` at the `ACQUISITION_DISPOSAL` stage.
- On failure the stage still persists `AcquisitionDisposalProjector.projection()` -- the lots/disposals produced up to the failing event. Event application is not atomic, so this partial snapshot may be incoherent (e.g. a disposal recorded without its event's acquisitions) and is intended only as debug output alongside the `FAILED` `SystemState`.
- Tax-event generation and the weekly summary remain unreachable dead code below the `COMPLETED` return, pending a future `TAX_COMPUTATION` stage.

### Price services
- `src/services/price_service.py` implements the domain `PriceProvider`, resolving `base -> quote`
  as a cross-rate through a single configured numeraire pivot (USD), with stablecoins pegged to
  their fiat currency and directional edges cached in SQLite (`src/db/price_cache.py`).
- `src/services/price_resolver.py` only routes a fetch to the owning provider (fiat vs crypto).
- Pricing contracts and records live in `src/domain/pricing.py`; provider HTTP clients live in
  `src/clients/`. Pricing model constants (numeraire, fiat codes, stable pegs) live in `config`.

### Price overrides
- `src/domain/price_override.py` owns both the `PriceOverride` model and `validate_overrides`, which
  checks each override against the corrected events (origin must match one; asset must appear in its
  legs) and raises `PriceOverrideValidationError` listing every problem.
- Overrides live in their own durable store (`artifacts/price_overrides.db`, `src/db/price_overrides.py`),
  a sibling of `corrections.db`. A unique constraint on `(origin_location, origin_external_id, asset_id)`
  makes two competing rates for one asset unrepresentable, so `PriceOverrideRepository.rates_by_origin()`
  can regroup rows for valuation without silently dropping one. `POST /price-overrides` maps that
  constraint's `IntegrityError` to a `409`.
- Valuation consults an override before the price provider and then treats the rate as an ordinary
  known one, so it feeds mid-point rebalancing and remainder solving like a fetched rate.

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
  - `uv run --group dev pytest -s tests/domain/acquisition_disposal_test.py` for running a domain test file;

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
