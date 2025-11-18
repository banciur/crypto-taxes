from __future__ import annotations

import argparse
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Sequence

from domain.inventory import InventoryEngine, OpenLotSnapshot
from importers.kraken_importer import KrakenImporter
from services.coindesk_source import CoinDeskSource
from services.open_exchange_rates_source import OpenExchangeRatesSource
from services.price_service import PriceService
from services.price_sources import HybridPriceSource
from services.price_store import JsonlPriceStore

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


def run(csv_path: Path, cache_dir: Path, *, market: str, aggregate_minutes: int) -> None:
    importer = KrakenImporter(str(csv_path))
    events = importer.load_events()
    print(f"Imported {len(events)} events from {csv_path}")

    price_service = build_price_service(cache_dir, market=market, aggregate_minutes=aggregate_minutes)
    engine = InventoryEngine(price_provider=price_service)
    result = engine.process(events)

    print("Inventory summary:")
    print(f"  Acquisition lots: {len(result.acquisition_lots)}")
    print(f"  Disposal links:   {len(result.disposal_links)}")
    print(f"  Open inventory entries: {len(result.open_inventory)}")
    print()
    summarize_open_inventory(result.open_inventory)


def summarize_open_inventory(open_inventory: Iterable[OpenLotSnapshot]) -> None:
    totals: defaultdict[str, Decimal] = defaultdict(Decimal)
    counts: defaultdict[str, int] = defaultdict(int)
    for lot in open_inventory:
        if lot.quantity_remaining <= 0:
            continue
        totals[lot.asset_id] += lot.quantity_remaining
        counts[lot.asset_id] += 1

    print("Open inventory by asset:")

    for asset in sorted(totals):
        print(f"  {asset:<8} qty={totals[asset]} lots={counts[asset]}")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run Kraken importer and inventory engine.")
    parser.add_argument("--csv", type=Path, default=Path("data/kraken-ledger.csv"))
    parser.add_argument("--price-cache-dir", type=Path, default=PROJECT_ROOT / ".cache" / "kraken_prices")
    parser.add_argument("--market", default="kraken")
    parser.add_argument("--aggregate", type=int, default=60)
    args = parser.parse_args(argv)
    run(args.csv, args.price_cache_dir, market=args.market, aggregate_minutes=args.aggregate)


if __name__ == "__main__":
    main()
