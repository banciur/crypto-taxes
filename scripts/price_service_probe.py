# flake8: noqa E402
# Run via uv for access to dev deps, e.g.:
# uv run scripts/price_service_probe.py --base BTC --quote USD --timestamp 2024-01-01T00:00:00Z
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List

# Ensure the src directory is importable when the script is invoked via uv/python directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from services.price_service import PriceService
from services.price_sources import CoinDeskPriceSource, HybridPriceSource, OpenExchangeRatesPriceSource
from services.price_store import JsonlPriceStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe PriceService caching with the CoinDesk source.")
    parser.add_argument("--base", default="BTC", help="Base asset symbol (default: BTC).")
    parser.add_argument("--quote", default="USD", help="Quote asset symbol (default: USD).")
    parser.add_argument("--market", default="coinbase", help="CoinDesk market identifier.")
    parser.add_argument(
        "--aggregate",
        type=int,
        default=60,
        help="Bucket size in minutes (matches CoinDeskPriceSource aggregate_minutes, default 60).",
    )
    parser.add_argument(
        "--timestamp",
        action="append",
        dest="timestamps",
        help="Timestamp to query (ISO8601 or unix). Can be repeated; defaults to now, same-now, and now-1h.",
    )
    parser.add_argument(
        "--store-dir",
        default=str(PROJECT_ROOT / ".cache" / "price_service_probe"),
        help="Directory to persist JsonlPriceStore data (default: .cache/price_service_probe).",
    )
    return parser.parse_args()


def load_timestamp(raw: str) -> datetime:
    try:
        as_int = int(raw)
        return datetime.fromtimestamp(as_int, tz=timezone.utc)
    except ValueError:
        pass

    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class LoggingCoinDeskPriceSource(CoinDeskPriceSource):
    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self.fetch_count = 0

    def fetch_snapshot(self, base_id: str, quote_id: str, timestamp: datetime):  # type: ignore[override]
        self.fetch_count += 1
        print(
            f"[source] fetch #{self.fetch_count} for {base_id.upper()}-{quote_id.upper()} "
            f"at {timestamp.astimezone(timezone.utc).isoformat()} UTC",
        )
        return super().fetch_snapshot(base_id, quote_id, timestamp)


class LoggingOpenExchangeRatesPriceSource(OpenExchangeRatesPriceSource):
    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self.fetch_count = 0

    def fetch_snapshot(self, base_id: str, quote_id: str, timestamp: datetime):  # type: ignore[override]
        self.fetch_count += 1
        print(
            f"[fiat-source] fetch #{self.fetch_count} for {base_id.upper()}-{quote_id.upper()} "
            f"at {timestamp.astimezone(timezone.utc).isoformat()} UTC",
        )
        return super().fetch_snapshot(base_id, quote_id, timestamp)


def default_timestamps(now: datetime) -> list[datetime]:
    return [now, now, now - timedelta(hours=1)]


def main() -> None:
    args = parse_args()

    now = datetime.now(timezone.utc)
    raw_timestamps: Iterable[str] | None = args.timestamps
    timestamps: List[datetime]
    if raw_timestamps:
        timestamps = [load_timestamp(raw) for raw in raw_timestamps]
    else:
        timestamps = default_timestamps(now)

    store_path = Path(args.store_dir)
    store_path.mkdir(parents=True, exist_ok=True)
    store = JsonlPriceStore(root_dir=store_path)
    crypto_source = LoggingCoinDeskPriceSource(
        market=args.market,
        aggregate_minutes=args.aggregate,
    )
    fiat_source = LoggingOpenExchangeRatesPriceSource(app_id=config().open_exchange_rates_app_id)
    hybrid_source = HybridPriceSource(
        crypto_source=crypto_source, fiat_source=fiat_source, fiat_currency_codes=("EUR", "PLN", "USD")
    )
    service = PriceService(source=hybrid_source, store=store)

    print(f"Using store at {store_path}")
    combined_fetches = lambda: crypto_source.fetch_count + fiat_source.fetch_count
    for idx, ts in enumerate(timestamps, start=1):
        before_fetches = combined_fetches()
        rate = service.rate(args.base, args.quote, timestamp=ts)
        after_fetches = combined_fetches()
        cache_hit = before_fetches == after_fetches
        status = "cache-hit" if cache_hit else "fetched"
        print(
            f"[request {idx}] {args.base.upper()}-{args.quote.upper()} @ {ts.astimezone(timezone.utc).isoformat()} "
            f"=> {rate} ({status})",
        )


if __name__ == "__main__":
    main()
