from __future__ import annotations

import argparse
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Sequence

from domain.inventory import InventoryEngine, InventoryResult, OpenLotSnapshot
from importers.kraken_importer import KrakenImporter
from services.coindesk_source import CoinDeskSource
from services.open_exchange_rates_source import OpenExchangeRatesSource
from services.price_service import PriceService
from services.price_sources import HybridPriceSource
from services.price_store import JsonlPriceStore
from utils.formatting import format_currency, format_decimal

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

    print_inventory_summary(result, price_service=price_service)


def print_inventory_summary(result: InventoryResult, *, price_service: PriceService) -> None:
    print("Inventory summary:")
    print(f"  Acquisition lots: {len(result.acquisition_lots)}")
    print(f"  Disposal links:   {len(result.disposal_links)}")
    print(f"  Open inventory entries: {len(result.open_inventory)}")
    print()
    summarize_open_inventory(result.open_inventory, price_service=price_service)


def summarize_open_inventory(
    open_inventory: Iterable[OpenLotSnapshot],
    *,
    price_service: PriceService,
) -> None:
    totals: defaultdict[str, Decimal] = defaultdict(Decimal)
    counts: defaultdict[str, int] = defaultdict(int)
    for lot in open_inventory:
        if lot.quantity_remaining <= 0:
            continue
        totals[lot.asset_id] += lot.quantity_remaining
        counts[lot.asset_id] += 1

    print("Open inventory by asset:")
    if not totals:
        print("  (empty)")
        return

    header = f"{'Asset':<8} {'Quantity':>16} {'Value EUR':>12} {'Lots':>4}"
    print(header)
    print("-" * len(header))

    total_value_eur = Decimal("0")
    for asset in sorted(totals):
        rate = price_service.rate(asset, InventoryEngine.EUR_ASSET_ID)
        value = totals[asset] * rate
        total_value_eur += value
        print(
            f"{asset:<8} {format_decimal(totals[asset]):>16} {format_currency(value):>12} {counts[asset]:>4}",
        )

    print("-" * len(header))
    print(f"{'TOTAL':<8} {'':>16} {format_currency(total_value_eur):>12} {'':>4}")


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
