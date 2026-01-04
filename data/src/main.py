from __future__ import annotations

import argparse
import logging
from pathlib import Path
from time import perf_counter
from typing import Sequence

from corrections.seed_events import apply_seed_event_corrections
from db.db import init_db
from db.repositories import (
    AcquisitionLotRepository,
    CorrectedLedgerEventRepository,
    DisposalLinkRepository,
    LedgerEventRepository,
    SeedEventRepository,
    TaxEventRepository,
)
from domain.inventory import InventoryEngine, InventoryResult
from domain.ledger import WalletId
from domain.wallet_balance_tracker import WalletBalanceTracker
from importers.kraken import KrakenImporter
from importers.moralis import MoralisImporter
from importers.seed_events import load_seed_events
from services.coindesk_source import CoinDeskSource
from services.open_exchange_rates_source import OpenExchangeRatesSource
from services.price_service import PriceService
from services.price_sources import HybridPriceSource
from services.price_store import JsonlPriceStore
from utils.inventory_summary import compute_inventory_summary, render_inventory_summary
from utils.tax_summary import compute_weekly_tax_summary, generate_tax_events, render_weekly_tax_summary

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
DB_FILE = REPO_ROOT / "crypto_taxes.db"

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
    logger.info("Initializing DB at %s", DB_FILE)
    session = init_db(reset=True, db_file=DB_FILE)
    event_repository = LedgerEventRepository(session)
    corrected_event_repository = CorrectedLedgerEventRepository(session)
    seed_event_repository = SeedEventRepository(session)
    lot_repository = AcquisitionLotRepository(session)
    disposal_repository = DisposalLinkRepository(session)
    tax_event_repository = TaxEventRepository(session)

    wallet_balance_tracker = WalletBalanceTracker()
    price_service = build_price_service(cache_dir, market=market, aggregate_minutes=aggregate_minutes)
    engine = InventoryEngine(price_provider=price_service, wallet_balance_tracker=wallet_balance_tracker)

    kraken_importer = KrakenImporter(str(csv_path))
    moralis_importer = MoralisImporter()

    owned_wallets: set[WalletId] = set()
    owned_wallets.add(KrakenImporter.WALLET_ID)

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

    events = [*kraken_events, *moralis_events]
    events.sort(key=lambda e: e.timestamp)
    logger.info("Persisting %d raw events", len(events))
    persist_started = perf_counter()
    event_repository.create_many(events)
    logger.info("Persisted raw events in %.2fs", perf_counter() - persist_started)

    # Apply corrections
    logger.info("Applying seed event corrections to %d raw events", len(events))
    corrections_started = perf_counter()
    corrected_events = apply_seed_event_corrections(raw_events=events, seed_events=seed_events)
    logger.info(
        "Applied corrections: %d corrected events in %.2fs",
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
        owned_wallets,
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
    parser = argparse.ArgumentParser(description="Run Kraken importer and inventory engine.")
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
