# flake8: noqa E402
# Run via: uv run scripts/run_kraken_inventory.py --csv data/kraken-ledger.csv
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from decimal import Decimal

from domain.inventory import InventoryEngine
from importers.kraken_importer import KrakenImporter
from services.price_service import PriceService
from services.price_sources import HybridPriceSource
from services.coindesk_source import CoinDeskSource
from services.open_exchange_rates_source import OpenExchangeRatesSource
from services.price_store import JsonlPriceStore


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


def summarize_assets(events) -> None:
    balances = defaultdict(Decimal)
    for event in events:
        for leg in event.legs:
            balances[leg.asset_id] += leg.quantity
    if not balances:
        print("No asset balances to report.")
        return
    print("Asset balances (including fees):")
    printed = False
    for asset, qty in sorted(balances.items()):
        if qty == 0:
            continue
        printed = True
        print(f"  {asset:<8} {qty}")
    if not printed:
        print("  (all zero)")


def run(csv_path: Path, cache_dir: Path, *, market: str, aggregate_minutes: int) -> None:
    importer = KrakenImporter(str(csv_path))
    events = importer.load_events()
    print(f"Imported {len(events)} events from {csv_path}")

    price_service = build_price_service(cache_dir, market=market, aggregate_minutes=aggregate_minutes)
    engine = InventoryEngine(price_provider=price_service)
    result = engine.process(events)

    summarize_assets(events)
    print("\nInventory summary:")
    print(f"  Acquisition lots: {len(result.acquisition_lots)}")
    print(f"  Disposal links:   {len(result.disposal_links)}")
    if result.open_inventory:
        print(f"  Open inventory entries: {len(result.open_inventory)}")
    else:
        print("  No open inventory entries")


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run Kraken importer and inventory engine.")
    parser.add_argument("--csv", type=Path, default=Path("data/kraken-ledger.csv"))
    parser.add_argument("--price-cache-dir", type=Path, default=PROJECT_ROOT / ".cache" / "kraken_prices")
    parser.add_argument("--market", default="kraken")
    parser.add_argument("--aggregate", type=int, default=60)
    args = parser.parse_args(argv)
    run(args.csv, args.price_cache_dir, market=args.market, aggregate_minutes=args.aggregate)


if __name__ == "__main__":
    main()
