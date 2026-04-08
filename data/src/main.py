from __future__ import annotations

import argparse
import logging
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
    config,
)
from corrections.ingestion import apply_ingestion_corrections
from db.ledger_corrections import CorrectionsBase, LedgerCorrectionRepository
from db.models import Base
from db.repositories import (
    AcquisitionLotRepository,
    CorrectedLedgerEventRepository,
    DisposalLinkRepository,
    LedgerEventRepository,
    TaxEventRepository,
)
from db.session import init_db_session
from db.tx_cache_coinbase import CoinbaseCacheRepository
from db.tx_cache_common import init_transactions_cache_db
from db.tx_cache_moralis import MoralisCacheRepository
from db.wallet_projection import WalletProjectionRepository
from domain.acquisition_disposal import AcquisitionDisposalProjector
from domain.ledger import LedgerEvent
from domain.wallet_projection import WalletProjector
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
    lot_repository = AcquisitionLotRepository(events_session)
    disposal_repository = DisposalLinkRepository(events_session)
    tax_event_repository = TaxEventRepository(events_session)
    correction_repository = LedgerCorrectionRepository(corrections_session)

    price_service = build_price_service(cache_dir, market=market, aggregate_minutes=aggregate_minutes)
    acquisition_disposal_projector = AcquisitionDisposalProjector(price_provider=price_service)

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

    # Get raw events
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

    # Apply corrections
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

    # Save corrections
    logger.info("Persisting corrected events")
    corrected_started = perf_counter()
    corrected_event_repository.create_many(corrected_events)
    logger.info("Persisted corrected events in %.2fs", perf_counter() - corrected_started)

    corrected_events = corrected_event_repository.list()
    logger.info("Rebuilding wallet tracking from %d corrected events", len(corrected_events))
    wallet_projection_state = WalletProjector().project(corrected_events)
    wallet_projection_repository.replace(wallet_projection_state)
    logger.info(
        "Persisted wallet projection state with status=%s",
        wallet_projection_state.status.value,
    )
    return  # just for now
    # Process stuff
    acquisition_disposal_projection = acquisition_disposal_projector.project(events)  # type: ignore[unreachable]
    lot_repository.create_many(acquisition_disposal_projection.acquisition_lots)
    disposal_repository.create_many(acquisition_disposal_projection.disposal_links)
    tax_events = generate_tax_events(acquisition_disposal_projection, events)
    tax_event_repository.create_many(tax_events)
    tax_events = tax_event_repository.list()

    # Print summary
    print(f"Imported {len(events)} events from {csv_path}")
    weekly_tax = compute_weekly_tax_summary(tax_events, acquisition_disposal_projection, events)
    render_weekly_tax_summary(weekly_tax)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run Kraken, Stakewise, Lido, Coinbase, and Moralis importers.")
    parser.add_argument("--csv", type=Path, default=ARTIFACTS_DIR / "kraken-ledger.csv")
    parser.add_argument("--price-cache-dir", type=Path, default=PROJECT_ROOT / ".cache" / "kraken_prices")
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
