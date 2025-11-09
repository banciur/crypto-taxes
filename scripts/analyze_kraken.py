# flake8: noqa E402
# Run via uv for tooling access, e.g.:
# uv run scripts/analyze_kraken.py --market kraken --aggregate 60
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from domain.inventory import InventoryEngine, InventoryError
from domain.ledger import LedgerEvent
from domain.pricing import PriceProvider
from importers.kraken_importer import KrakenImporter, KrakenLedgerEntry
from services.coindesk_source import CoinDeskAPIError, CoinDeskSource
from services.open_exchange_rates_source import OpenExchangeRatesSource
from services.price_service import PriceService
from services.price_sources import HybridPriceSource
from services.price_store import JsonlPriceStore

ASSET_ALIASES: dict[str, str] = {
    "ETH2": "ETH",
    "ETH2.S": "ETH",
    "DOT.S": "DOT",
    "DOT28.S": "DOT",
    "KAVA.S": "KAVA",
    "KAVA21.S": "KAVA",
    "USDC.M": "USDC",
}


class AliasPriceProvider(PriceProvider):
    def __init__(self, delegate: PriceProvider, aliases: dict[str, str]) -> None:
        self._delegate = delegate
        self._aliases = {key.upper(): value.upper() for key, value in aliases.items()}

    def rate(self, base_id: str, quote_id: str, timestamp: datetime) -> Decimal:  # type: ignore[override]
        mapped_base = self._aliases.get(base_id.upper(), base_id.upper())
        mapped_quote = self._aliases.get(quote_id.upper(), quote_id.upper())
        return self._delegate.rate(mapped_base, mapped_quote, timestamp)


def _categorize_skip(importer: KrakenImporter, entries: list[KrakenLedgerEntry]) -> str:
    is_allocation_pair = getattr(importer, "_is_allocation_pair", None)
    if callable(is_allocation_pair):
        try:
            if is_allocation_pair(entries):
                return "earn_allocation_pair"
        except Exception:  # pragma: no cover - best-effort categorization
            pass
    if len(entries) == 1:
        entry = entries[0]
        subtype = entry.subtype or ""
        return f"single_unhandled:{entry.type}:{subtype}"
    if len(entries) == 2:
        types = "+".join(sorted(entry.type for entry in entries))
        subtypes = "+".join(sorted((entry.subtype or "") for entry in entries))
        return f"double_unhandled:{types}:{subtypes}"
    return f"multi_unhandled:{len(entries)}"


def _build_price_provider(cache_dir: Path, *, market: str, aggregate_minutes: int) -> PriceProvider:
    cache_dir.mkdir(parents=True, exist_ok=True)
    store = JsonlPriceStore(root_dir=cache_dir)
    crypto_source = CoinDeskSource(
        market=market,
        aggregate_minutes=aggregate_minutes,
    )
    fiat_source = OpenExchangeRatesSource()
    hybrid_source = HybridPriceSource(
        crypto_source=crypto_source,
        fiat_source=fiat_source,
        fiat_currency_codes=("EUR", "PLN", "USD"),
    )
    service = PriceService(source=hybrid_source, store=store)
    return AliasPriceProvider(service, ASSET_ALIASES)


def analyze(path: Path, price_cache_dir: Path, *, market: str, aggregate_minutes: int) -> None:
    importer = KrakenImporter(str(path))
    entries = importer._read_entries()  # type: ignore[attr-defined]
    groups = importer._group_by_refid(entries)  # type: ignore[attr-defined]

    events = []
    event_counts: Counter[str] = Counter()
    skipped_counts: Counter[str] = Counter()
    errors: list[tuple[str, str]] = []

    for refid, group in groups.items():
        try:
            event = importer._build_event(group)  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover
            errors.append((refid, str(exc)))
            continue

        if event is None:
            skipped_counts[_categorize_skip(importer, group)] += 1
        else:
            event_counts[event.event_type.value] += 1
            events.append(event)

    events.sort(key=lambda evt: evt.timestamp)
    portfolio_balances = _portfolio_balances(events)

    print(f"Ledger rows: {len(entries)}")
    print(f"Refid groups: {len(groups)}")
    print(f"Events emitted: {len(events)}")
    print("By event type:")
    for event_type, count in sorted(event_counts.items()):
        print(f"  {event_type:<12} {count}")

    total_skipped = sum(skipped_counts.values())
    print(f"\nSkipped groups: {total_skipped}")
    for reason, count in skipped_counts.most_common():
        print(f"  {reason:<40} {count}")

    if errors:
        print("\nErrors:")
        for refid, message in errors:
            print(f"  {refid}: {message}")

    if portfolio_balances:
        print("\nNet ledger balances (all legs):")
        for asset, qty in sorted(portfolio_balances.items()):
            print(f"  {asset:<8} {qty}")

    if not events:
        print("\nNo events produced; skipping inventory processing.")
        return

    print(f"\nRunning inventory engine with live price service (market={market}, agg={aggregate_minutes}m)...")
    price_provider = _build_price_provider(price_cache_dir, market=market, aggregate_minutes=aggregate_minutes)
    engine = InventoryEngine(price_provider=price_provider)
    try:
        result = engine.process(events)
    except CoinDeskAPIError as exc:
        print(
            "  Failed to complete inventory processing due to CoinDesk API error "
            f"({exc}). Cached prices remain in {price_cache_dir}."
        )
        print("  Try rerunning later or provide API access with a higher rate limit.")
        return
    except InventoryError as exc:
        print(f"  Inventory processing aborted: {exc}")
        return

    print("Inventory summary:")
    print(f"  Acquisition lots: {len(result.acquisition_lots)}")
    print(f"  Disposal links:   {len(result.disposal_links)}")
    print(f"  Open inventory:   {len(result.open_inventory)} entries")

    open_by_asset = defaultdict(Decimal)
    for snapshot in result.open_inventory:
        open_by_asset[snapshot.asset_id] += snapshot.quantity_remaining

    if open_by_asset:
        print("  Asset balances:")
        for asset, qty in sorted(open_by_asset.items()):
            print(f"    {asset:<8} {qty}")


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Analyze Kraken ledger CSV, emit events, and run inventory processing."
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path("data/kraken-ledger.csv"),
        help="Path to Kraken ledger CSV (default: data/kraken-ledger.csv)",
    )
    parser.add_argument(
        "--price-cache-dir",
        type=Path,
        default=PROJECT_ROOT / ".cache" / "kraken_prices",
        help="Directory to persist price snapshots (default: .cache/kraken_prices)",
    )
    parser.add_argument(
        "--market",
        default="kraken",
        help="CoinDesk market identifier for crypto pairs (default: kraken)",
    )
    parser.add_argument(
        "--aggregate",
        type=int,
        default=60,
        help="CoinDesk aggregate minutes per candle (default: 60)",
    )
    args = parser.parse_args(argv)
    analyze(args.path, args.price_cache_dir, market=args.market, aggregate_minutes=args.aggregate)


def _portfolio_balances(events: list[LedgerEvent]) -> dict[str, Decimal]:
    balances: dict[str, Decimal] = defaultdict(Decimal)
    for event in events:
        for leg in event.legs:
            balances[leg.asset_id] += leg.quantity
    cleaned = {asset: qty for asset, qty in balances.items() if qty != 0}
    return cleaned


if __name__ == "__main__":  # pragma: no cover
    main()
