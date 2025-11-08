# flake8: noqa E402
# Run via uv to load project deps, e.g.:
# uv run scripts/open_exchange_rates_probe.py --base EUR --quote USD --date 2024-01-01
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

# Ensure the src directory is importable when the script is invoked via uv/python directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import config
from services.open_exchange_rates_client import OpenExchangeRatesClient
from services.price_sources import OpenExchangeRatesPriceSource


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch historical fiat FX rates from Open Exchange Rates.")
    parser.add_argument("--base", default="EUR", help="Base currency code (default: EUR).")
    parser.add_argument("--quote", default="USD", help="Quote currency code (default: USD).")
    parser.add_argument(
        "--date",
        default=None,
        help="Historical date (YYYY-MM-DD). Defaults to current UTC date.",
    )
    return parser.parse_args()


def parse_date(raw: str | None) -> date:
    if not raw:
        return datetime.now(timezone.utc).date()
    return datetime.fromisoformat(raw).date()


def main() -> None:
    args = parse_args()

    target_date = parse_date(args.date)
    client = OpenExchangeRatesClient(app_id=config().open_exchange_rates_app_id)
    source = OpenExchangeRatesPriceSource(client=client)

    # Use midnight UTC because the price source buckets by calendar day.
    ts = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    quote = source.fetch_snapshot(args.base, args.quote, timestamp=ts)

    payload: dict[str, Any] = {
        "requested_pair": f"{args.base.upper()}-{args.quote.upper()}",
        "requested_date": target_date.isoformat(),
        "snapshot_timestamp": quote.timestamp.isoformat(),
        "source": quote.source,
        "rate": str(quote.rate),
        "valid_from": quote.valid_from.isoformat(),
        "valid_to": quote.valid_to.isoformat(),
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
