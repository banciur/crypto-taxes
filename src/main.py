from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from db.db import init_db
from db.repositories import LedgerEventRepository
from domain.inventory import InventoryEngine, InventoryResult
from importers.kraken_importer import KrakenImporter
from services.coindesk_source import CoinDeskSource
from services.open_exchange_rates_source import OpenExchangeRatesSource
from services.price_service import PriceService
from services.price_sources import HybridPriceSource
from services.price_store import JsonlPriceStore
from utils.debug_dump import dump_inventory_debug
from utils.inventory_summary import compute_inventory_summary, render_inventory_summary
from utils.seed_events import load_seed_events
from utils.tax_summary import compute_weekly_tax_summary, generate_tax_events, render_weekly_tax_summary

PROJECT_ROOT = Path(__file__).resolve().parents[1]


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


def run(csv_path: Path, cache_dir: Path, *, market: str, aggregate_minutes: int, seed_csv: Path) -> None:
    session = init_db(reset=True)
    repository = LedgerEventRepository(session)

    importer = KrakenImporter(str(csv_path))
    price_service = build_price_service(cache_dir, market=market, aggregate_minutes=aggregate_minutes)
    engine = InventoryEngine(price_provider=price_service)

    seed_events = load_seed_events(seed_csv)
    events = seed_events + importer.load_events()
    events.sort(key=lambda event: event.timestamp)
    for event in events:
        repository.create(event)
    events = repository.list()

    inventory = engine.process(events)
    tax_events = generate_tax_events(inventory, events)

    dump_inventory_debug(events, inventory)

    print(f"Imported {len(events)} events from {csv_path}")
    print_base_inventory_summary(inventory)
    inventory_summary = compute_inventory_summary(inventory.open_inventory, price_provider=price_service)
    render_inventory_summary(inventory_summary)
    weekly_tax = compute_weekly_tax_summary(tax_events, inventory, events)
    render_weekly_tax_summary(weekly_tax)


def print_base_inventory_summary(result: InventoryResult) -> None:
    print("Inventory summary:")
    print(f"  Acquisition lots: {len(result.acquisition_lots)}")
    print(f"  Disposal links:   {len(result.disposal_links)}")
    print(f"  Open inventory entries: {len(result.open_inventory)}")


def main(argv: Sequence[str] | None = None) -> None:
    # logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description="Run Kraken importer and inventory engine.")
    parser.add_argument("--csv", type=Path, default=Path("data/kraken-ledger.csv"))
    parser.add_argument("--price-cache-dir", type=Path, default=PROJECT_ROOT / ".cache" / "kraken_prices")
    parser.add_argument("--market", default="kraken")
    parser.add_argument("--aggregate", type=int, default=60)
    parser.add_argument("--seed-csv", type=Path, default=Path("data/seed_lots.csv"))
    args = parser.parse_args(argv)
    run(args.csv, args.price_cache_dir, market=args.market, aggregate_minutes=args.aggregate, seed_csv=args.seed_csv)


if __name__ == "__main__":
    main()
