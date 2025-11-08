# flake8: noqa E402
# Run via uv so project deps are loaded, e.g.:
# uv run scripts/coindesk_probe.py --base BTC --quote USD --market coinbase
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure the src directory is importable when the script is invoked via uv/python directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import config
from services.price_sources import CoinDeskPriceSource


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch a live CoinDesk spot price snapshot.")
    parser.add_argument("--base", default="BTC", help="Base asset symbol, e.g. BTC.")
    parser.add_argument("--quote", default="USD", help="Quote asset symbol, e.g. USD.")
    parser.add_argument(
        "--market",
        default="coinbase",
        help="Exchange market identifier as per CoinDesk API (default: coinbase).",
    )
    parser.add_argument(
        "--timestamp",
        help="Optional ISO8601 timestamp to request (default: current UTC time).",
    )
    parser.add_argument(
        "--aggregate",
        type=int,
        default=60,
        help="Bucket size in minutes for CoinDesk histo API (default: 60 = 1 hour).",
    )
    return parser.parse_args()


def load_timestamp(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)

    try:
        # Allow integer UNIX epoch values
        as_int = int(raw)
        return datetime.fromtimestamp(as_int, tz=timezone.utc)
    except ValueError:
        pass

    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def main() -> None:
    args = parse_args()

    ts = load_timestamp(args.timestamp)
    source = CoinDeskPriceSource(
        api_key=config().coindesk_api_key,
        market=args.market,
        aggregate_minutes=args.aggregate,
    )
    quote = source.fetch_snapshot(args.base, args.quote, timestamp=ts)
    payload: dict[str, Any] = {
        "timestamp": quote.timestamp.isoformat(),
        "base": quote.base_id,
        "quote": quote.quote_id,
        "rate": str(quote.rate),
        "source": quote.source,
        "valid_from": quote.valid_from.isoformat(),
        "valid_to": quote.valid_to.isoformat(),
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
