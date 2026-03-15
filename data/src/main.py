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
from corrections.seed_events import apply_seed_event_corrections
from corrections.spam import apply_spam_corrections
from db.corrections_common import init_corrections_db
from db.corrections_spam import SpamCorrectionRepository
from db.db import init_db
from db.repositories import (
    AcquisitionLotRepository,
    CorrectedLedgerEventRepository,
    DisposalLinkRepository,
    LedgerEventRepository,
    SeedEventRepository,
    TaxEventRepository,
)
from db.tx_cache_coinbase import CoinbaseCacheRepository
from db.tx_cache_common import init_transactions_cache_db
from db.tx_cache_moralis import MoralisCacheRepository
from domain.inventory import InventoryEngine, InventoryResult
from domain.ledger import AccountChainId
from domain.wallet_balance_tracker import WalletBalanceTracker
from importers.coinbase import COINBASE_ACCOUNT_ID, CoinbaseImporter
from importers.kraken import KRAKEN_ACCOUNT_ID, KrakenImporter
from importers.moralis import MoralisImporter
from importers.seed_events import load_seed_events
from services.coinbase import CoinbaseService
from services.coindesk_source import CoinDeskSource
from services.moralis import MoralisService
from services.open_exchange_rates_source import OpenExchangeRatesSource
from services.price_service import PriceService
from services.price_sources import HybridPriceSource
from services.price_store import JsonlPriceStore
from utils.inventory_summary import compute_inventory_summary, render_inventory_summary
from utils.tax_summary import compute_weekly_tax_summary, generate_tax_events, render_weekly_tax_summary

logger = logging.getLogger(__name__)


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


def run(
    csv_path: Path,
    cache_dir: Path,
    *,
    market: str,
    aggregate_minutes: int,
    seed_csv: Path,
) -> None:
    # Setup components
    logger.info("Initializing DB at %s", DB_PATH)
    session = init_db(reset=True, db_path=DB_PATH)
    corrections_session = init_corrections_db(db_path=CORRECTIONS_DB_PATH, reset=False)
    event_repository = LedgerEventRepository(session)
    corrected_event_repository = CorrectedLedgerEventRepository(session)
    seed_event_repository = SeedEventRepository(session)
    lot_repository = AcquisitionLotRepository(session)
    disposal_repository = DisposalLinkRepository(session)
    tax_event_repository = TaxEventRepository(session)
    spam_correction_repository = SpamCorrectionRepository(corrections_session)

    wallet_balance_tracker = WalletBalanceTracker()
    price_service = build_price_service(cache_dir, market=market, aggregate_minutes=aggregate_minutes)
    engine = InventoryEngine(price_provider=price_service, wallet_balance_tracker=wallet_balance_tracker)

    kraken_importer = KrakenImporter(str(csv_path))

    tx_cache_session = init_transactions_cache_db(db_path=TRANSACTIONS_CACHE_DB_PATH)
    coinbase_service = CoinbaseService(
        CoinbaseClient(
            api_key=config().coinbase_key_name,
            api_secret=config().coinbase_key_prv,
        ),
        CoinbaseCacheRepository(tx_cache_session),
    )
    coinbase_importer = CoinbaseImporter(service=coinbase_service)

    accounts = load_accounts()
    moralis_importer = MoralisImporter(
        service=MoralisService(
            MoralisClient(api_key=config().moralis_api_key),
            MoralisCacheRepository(tx_cache_session),
            accounts=accounts,
        ),
        account_registry=AccountRegistry(accounts),
        spam_correction_repository=spam_correction_repository,
    )

    owned_accounts: set[AccountChainId] = {COINBASE_ACCOUNT_ID, KRAKEN_ACCOUNT_ID}

    # Get corrections
    logger.info("Loading seed events from %s", seed_csv)
    seed_started = perf_counter()
    seed_events = load_seed_events(seed_csv)
    seed_event_repository.create_many(seed_events)
    logger.info("Loaded and stored %d seed events in %.2fs", len(seed_events), perf_counter() - seed_started)

    # Get raw events
    logger.info("Importing Kraken events from %s", csv_path)
    kraken_started = perf_counter()
    kraken_events = kraken_importer.load_events()
    logger.info("Imported %d Kraken events in %.2fs", len(kraken_events), perf_counter() - kraken_started)

    logger.info("Importing Moralis events")
    moralis_started = perf_counter()
    moralis_events = moralis_importer.load_events()
    logger.info("Imported %d Moralis events in %.2fs", len(moralis_events), perf_counter() - moralis_started)

    logger.info("Importing Coinbase events")
    coinbase_started = perf_counter()
    coinbase_events = coinbase_importer.load_events()
    logger.info("Imported %d Coinbase events in %.2fs", len(coinbase_events), perf_counter() - coinbase_started)

    events = [*kraken_events, *moralis_events, *coinbase_events]
    events.sort(key=lambda e: e.timestamp)
    logger.info("Persisting %d raw events", len(events))
    persist_started = perf_counter()
    event_repository.create_many(events)
    logger.info("Persisted raw events in %.2fs", perf_counter() - persist_started)

    # Apply corrections
    spam_markers = spam_correction_repository.list()
    logger.info("Loaded %d active spam corrections", len(spam_markers))
    logger.info("Applying corrections to %d raw events", len(events))
    corrections_started = perf_counter()
    filtered_events = list(apply_spam_corrections(raw_events=events, spam_markers=spam_markers))
    logger.info("Removed %d spam raw events", len(events) - len(filtered_events))
    corrected_events = apply_seed_event_corrections(raw_events=filtered_events, seed_events=seed_events)
    logger.info(
        "Applied spam+seed corrections: %d corrected events in %.2fs",
        len(corrected_events),
        perf_counter() - corrections_started,
    )

    # Save corrections
    logger.info("Persisting corrected events")
    corrected_started = perf_counter()
    corrected_event_repository.create_many(corrected_events)
    logger.info("Persisted corrected events in %.2fs", perf_counter() - corrected_started)
    return  # just for now
    # Process stuff
    inventory = engine.process(events)  # type: ignore[unreachable]
    lot_repository.create_many(inventory.acquisition_lots)
    disposal_repository.create_many(inventory.disposal_links)
    # dump_inventory_debug(events, inventory)

    tax_events = generate_tax_events(inventory, events)
    tax_event_repository.create_many(tax_events)
    tax_events = tax_event_repository.list()

    # Print summary
    print(f"Imported {len(events)} events from {csv_path}")
    print_base_inventory_summary(inventory)
    inventory_summary = compute_inventory_summary(
        owned_accounts,
        wallet_balance_tracker=wallet_balance_tracker,
        price_provider=price_service,
    )
    render_inventory_summary(inventory_summary)
    weekly_tax = compute_weekly_tax_summary(tax_events, inventory, events)
    render_weekly_tax_summary(weekly_tax)


def print_base_inventory_summary(result: InventoryResult) -> None:
    print("Inventory summary:")
    print(f"  Acquisition lots: {len(result.acquisition_lots)}")
    print(f"  Disposal links:   {len(result.disposal_links)}")
    print(f"  Open inventory entries: {len(result.open_inventory)}")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run Coinbase, Kraken, and Moralis importers.")
    parser.add_argument("--csv", type=Path, default=ARTIFACTS_DIR / "kraken-ledger.csv")
    parser.add_argument("--price-cache-dir", type=Path, default=PROJECT_ROOT / ".cache" / "kraken_prices")
    parser.add_argument("--market", default="kraken")
    parser.add_argument("--aggregate", type=int, default=60)
    parser.add_argument("--seed-csv", type=Path, default=ARTIFACTS_DIR / "seed_lots.csv")
    args = parser.parse_args(argv)
    run(
        args.csv,
        args.price_cache_dir,
        market=args.market,
        aggregate_minutes=args.aggregate,
        seed_csv=args.seed_csv,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    main()
