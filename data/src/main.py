import argparse
import logging
import traceback as traceback_utils
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Sequence

from accounts import AccountRegistry, load_accounts
from clients.coinbase import CoinbaseClient
from clients.moralis import MoralisClient
from config import (
    ARTIFACTS_DIR,
    CORRECTIONS_DB_PATH,
    DB_PATH,
    PROJECT_ROOT,
    TRANSACTIONS_CACHE_DB_PATH,
    AppSettings,
    config,
)
from corrections.ingestion import apply_ingestion_corrections
from db.acquisition_disposal import AcquisitionDisposalProjectionRepository
from db.base import Base
from db.ledger_corrections import CorrectionsBase, LedgerCorrectionRepository
from db.ledger_events import CorrectedLedgerEventRepository, LedgerEventRepository
from db.session import init_db_session
from db.system_state import SystemStateRepository
from db.tax_events import TaxEventRepository
from db.tx_cache_coinbase import CoinbaseCacheRepository
from db.tx_cache_common import init_transactions_cache_db
from db.tx_cache_moralis import MoralisCacheRepository
from db.wallet_projection import WalletProjectionRepository
from domain.acquisition_disposal import AcquisitionDisposalProjection, AcquisitionDisposalProjector
from domain.ledger import LedgerEvent
from domain.pricing import PriceProvider
from domain.projection import ProjectionStatus
from domain.system_state import (
    SystemState,
    SystemStateError,
    SystemStateStage,
    SystemStateStatus,
)
from domain.wallet_projection import WalletProjector, WalletTrackingState
from importers.coinbase import CoinbaseImporter
from importers.kraken import KrakenImporter
from importers.lido import LidoImporter
from importers.moralis import MoralisImporter
from importers.stakewise import StakewiseImporter
from services.coinbase import CoinbaseService
from services.coindesk_source import CoinDeskSource
from services.moralis import MoralisService
from services.open_exchange_rates_source import OpenExchangeRatesSource
from services.price_service import PriceService
from services.price_sources import HybridPriceSource
from services.price_store import JsonlPriceStore
from utils.tax_summary import compute_weekly_tax_summary, generate_tax_events, render_weekly_tax_summary

logger = logging.getLogger(__name__)
STAKEWISE_CSV_GLOB = "Stakewise*.csv"
LIDO_CSV_PATH = ARTIFACTS_DIR / "lido.csv"
STAKING_REWARDS_WALLET_ENV_VAR = "STAKING_REWARDS_WALLET_ADDRESS"


def build_price_service(cache_dir: Path, *, market: str, aggregate_minutes: int) -> PriceService:
    cache_dir.mkdir(parents=True, exist_ok=True)
    store = JsonlPriceStore(root_dir=cache_dir)
    crypto_source = CoinDeskSource(market=market, aggregate_minutes=aggregate_minutes)
    fiat_source = OpenExchangeRatesSource()
    source = HybridPriceSource(
        crypto_source=crypto_source,
        fiat_source=fiat_source,
        fiat_currency_codes=("EUR", "PLN", "USD"),
    )
    return PriceService(source=source, store=store)


def load_stakewise_events(*, wallet_address: str | None) -> list[LedgerEvent]:
    if not wallet_address:
        logger.info("Skipping Stakewise import because %s is not configured", STAKING_REWARDS_WALLET_ENV_VAR)
        return []

    paths = sorted(ARTIFACTS_DIR.glob(STAKEWISE_CSV_GLOB))
    if not paths:
        logger.info("No Stakewise CSVs found under %s matching %s", ARTIFACTS_DIR, STAKEWISE_CSV_GLOB)
        return []

    logger.info("Importing Stakewise events from %d CSV file(s)", len(paths))
    importer = StakewiseImporter(paths, wallet_address=wallet_address)
    started = perf_counter()
    events = importer.load_events()
    logger.info("Imported %d Stakewise events in %.2fs", len(events), perf_counter() - started)
    return events


def load_lido_events(*, wallet_address: str | None) -> list[LedgerEvent]:
    if not wallet_address:
        logger.info("Skipping Lido import because %s is not configured", STAKING_REWARDS_WALLET_ENV_VAR)
        return []

    if not LIDO_CSV_PATH.exists():
        logger.info("No Lido CSV found at %s", LIDO_CSV_PATH)
        return []

    logger.info("Importing Lido events from %s", LIDO_CSV_PATH)
    importer = LidoImporter(LIDO_CSV_PATH, wallet_address=wallet_address)
    started = perf_counter()
    events = importer.load_events()
    logger.info("Imported %d Lido events in %.2fs", len(events), perf_counter() - started)
    return events


def _system_state_error_from_exception(error: Exception) -> SystemStateError:
    exception_type = type(error).__name__
    return SystemStateError(
        exception_type=exception_type,
        message=str(error) or exception_type,
        traceback="".join(traceback_utils.format_exception(type(error), error, error.__traceback__)),
    )


def _system_state_error_from_wallet_projection() -> SystemStateError:
    # Wallet projection failure is a projection status, not an exception; the failed event and blocking
    # issues are persisted and rendered separately by the wallet projection output.
    return SystemStateError(
        exception_type="WalletProjectionFailed",
        message="Wallet projection failed",
    )


def _run_system_state_stage[T](
    repository: SystemStateRepository,
    stage: SystemStateStage,
    *,
    started_at: datetime,
    action: Callable[[], T],
) -> T:
    repository.replace(
        SystemState(
            status=SystemStateStatus.RUNNING,
            stage=stage,
            started_at=started_at,
        )
    )

    try:
        return action()
    except Exception as error:
        repository.replace(
            SystemState(
                status=SystemStateStatus.FAILED,
                stage=stage,
                started_at=started_at,
                finished_at=datetime.now(UTC),
                error=_system_state_error_from_exception(error),
            )
        )
        raise


def _import_and_persist_raw_events(
    *,
    csv_path: Path,
    settings: AppSettings,
    event_repository: LedgerEventRepository,
    correction_repository: LedgerCorrectionRepository,
) -> list[LedgerEvent]:
    kraken_importer = KrakenImporter(str(csv_path))

    tx_cache_session = init_transactions_cache_db(db_path=TRANSACTIONS_CACHE_DB_PATH)
    coinbase_service = CoinbaseService(
        CoinbaseClient(
            api_key=settings.coinbase_key_name,
            api_secret=settings.coinbase_key_prv,
        ),
        CoinbaseCacheRepository(tx_cache_session),
    )
    coinbase_importer = CoinbaseImporter(service=coinbase_service)

    accounts = load_accounts()
    moralis_importer = MoralisImporter(
        service=MoralisService(
            MoralisClient(api_key=settings.moralis_api_key),
            MoralisCacheRepository(tx_cache_session),
            accounts=accounts,
        ),
        account_registry=AccountRegistry(accounts),
        correction_repository=correction_repository,
    )

    logger.info("Importing Kraken events from %s", csv_path)
    kraken_started = perf_counter()
    kraken_events = kraken_importer.load_events()
    logger.info("Imported %d Kraken events in %.2fs", len(kraken_events), perf_counter() - kraken_started)

    stakewise_events = load_stakewise_events(wallet_address=settings.staking_rewards_wallet_address)
    lido_events = load_lido_events(wallet_address=settings.staking_rewards_wallet_address)

    logger.info("Importing Moralis events")
    moralis_started = perf_counter()
    moralis_events = moralis_importer.load_events()
    logger.info("Imported %d Moralis events in %.2fs", len(moralis_events), perf_counter() - moralis_started)

    logger.info("Importing Coinbase events")
    coinbase_started = perf_counter()
    coinbase_events = coinbase_importer.load_events()
    logger.info("Imported %d Coinbase events in %.2fs", len(coinbase_events), perf_counter() - coinbase_started)

    events = [*kraken_events, *stakewise_events, *lido_events, *moralis_events, *coinbase_events]
    events.sort(key=lambda e: e.timestamp)
    logger.info("Persisting %d raw events", len(events))
    persist_started = perf_counter()
    event_repository.create_many(events)
    logger.info("Persisted raw events in %.2fs", perf_counter() - persist_started)
    return events


def _apply_and_persist_corrections(
    *,
    events: list[LedgerEvent],
    correction_repository: LedgerCorrectionRepository,
    corrected_event_repository: CorrectedLedgerEventRepository,
) -> list[LedgerEvent]:
    corrections = correction_repository.list()
    logger.info("Loaded %d active ledger corrections", len(corrections))

    logger.info("Applying corrections to %d raw events", len(events))
    corrections_started = perf_counter()
    corrected_events = apply_ingestion_corrections(
        raw_events=events,
        corrections=corrections,
    )
    logger.info(
        "Applied ledger corrections: %d corrected events in %.2fs",
        len(corrected_events),
        perf_counter() - corrections_started,
    )

    logger.info("Persisting corrected events")
    corrected_started = perf_counter()
    corrected_event_repository.create_many(corrected_events)
    logger.info("Persisted corrected events in %.2fs", perf_counter() - corrected_started)

    return corrected_event_repository.list()


def _rebuild_wallet_projection(
    *,
    corrected_events: list[LedgerEvent],
    wallet_projection_repository: WalletProjectionRepository,
) -> WalletTrackingState:
    logger.info("Rebuilding wallet tracking from %d corrected events", len(corrected_events))
    wallet_projection_state = WalletProjector().project(corrected_events)
    wallet_projection_repository.replace(wallet_projection_state)
    logger.info(
        "Persisted wallet projection state with status=%s",
        wallet_projection_state.status.value,
    )
    return wallet_projection_state


def _rebuild_acquisition_disposal_projection(
    *,
    corrected_events: list[LedgerEvent],
    price_service: PriceProvider,
    projection_repository: AcquisitionDisposalProjectionRepository,
) -> AcquisitionDisposalProjection:
    logger.info("Building acquisition/disposal projection from %d corrected events", len(corrected_events))
    projection = AcquisitionDisposalProjector(price_provider=price_service).project(corrected_events)
    projection_repository.replace(projection)
    logger.info(
        "Persisted acquisition/disposal projection with %d lots and %d disposals",
        len(projection.acquisition_lots),
        len(projection.disposal_links),
    )
    return projection


def run(
    csv_path: Path,
    cache_dir: Path,
    *,
    market: str,
    aggregate_minutes: int,
) -> None:
    # Setup components
    logger.info("Initializing DB at %s", DB_PATH)
    settings = config()
    events_session = init_db_session(db_path=DB_PATH, metadata=Base.metadata, reset=True)
    corrections_session = init_db_session(
        db_path=CORRECTIONS_DB_PATH,
        metadata=CorrectionsBase.metadata,
        reset=False,
    )
    event_repository = LedgerEventRepository(events_session)
    corrected_event_repository = CorrectedLedgerEventRepository(events_session)
    wallet_projection_repository = WalletProjectionRepository(events_session)
    acquisition_disposal_projection_repository = AcquisitionDisposalProjectionRepository(events_session)
    tax_event_repository = TaxEventRepository(events_session)
    system_state_repository = SystemStateRepository(events_session)
    correction_repository = LedgerCorrectionRepository(corrections_session)

    run_started_at = datetime.now(UTC)
    events = _run_system_state_stage(
        system_state_repository,
        SystemStateStage.RAW_IMPORT,
        started_at=run_started_at,
        action=lambda: _import_and_persist_raw_events(
            csv_path=csv_path,
            settings=settings,
            event_repository=event_repository,
            correction_repository=correction_repository,
        ),
    )
    corrected_events = _run_system_state_stage(
        system_state_repository,
        SystemStateStage.CORRECTIONS,
        started_at=run_started_at,
        action=lambda: _apply_and_persist_corrections(
            events=events,
            correction_repository=correction_repository,
            corrected_event_repository=corrected_event_repository,
        ),
    )
    wallet_projection_state = _run_system_state_stage(
        system_state_repository,
        SystemStateStage.WALLET_PROJECTION,
        started_at=run_started_at,
        action=lambda: _rebuild_wallet_projection(
            corrected_events=corrected_events,
            wallet_projection_repository=wallet_projection_repository,
        ),
    )
    if wallet_projection_state.status == ProjectionStatus.FAILED:
        system_state_repository.replace(
            SystemState(
                status=SystemStateStatus.FAILED,
                stage=SystemStateStage.WALLET_PROJECTION,
                started_at=run_started_at,
                finished_at=datetime.now(UTC),
                error=_system_state_error_from_wallet_projection(),
            )
        )
        return

    price_service = build_price_service(cache_dir, market=market, aggregate_minutes=aggregate_minutes)
    acquisition_disposal_projection = _run_system_state_stage(
        system_state_repository,
        SystemStateStage.ACQUISITION_DISPOSAL,
        started_at=run_started_at,
        action=lambda: _rebuild_acquisition_disposal_projection(
            corrected_events=corrected_events,
            price_service=price_service,
            projection_repository=acquisition_disposal_projection_repository,
        ),
    )

    system_state_repository.replace(
        SystemState(
            status=SystemStateStatus.COMPLETED,
            started_at=run_started_at,
            finished_at=datetime.now(UTC),
        )
    )
    return  # just for now
    # Process stuff
    tax_events = generate_tax_events(acquisition_disposal_projection, events)  # type: ignore[unreachable]
    tax_event_repository.create_many(tax_events)
    tax_events = tax_event_repository.list()

    # Print summary
    print(f"Imported {len(events)} events from {csv_path}")
    weekly_tax = compute_weekly_tax_summary(tax_events, acquisition_disposal_projection, events)
    render_weekly_tax_summary(weekly_tax)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run Kraken, Stakewise, Lido, Coinbase, and Moralis importers.")
    parser.add_argument("--csv", type=Path, default=ARTIFACTS_DIR / "kraken-ledger.csv")
    parser.add_argument("--price-cache-dir", type=Path, default=PROJECT_ROOT / ".cache" / "prices")
    parser.add_argument("--market", default="kraken")
    parser.add_argument("--aggregate", type=int, default=60)
    args = parser.parse_args(argv)
    run(
        args.csv,
        args.price_cache_dir,
        market=args.market,
        aggregate_minutes=args.aggregate,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    main()
