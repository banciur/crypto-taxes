# flake8: noqa: E402
import argparse
import json
import logging
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from clients.coinmarketcap import CoinMarketCapClient
from config import config
from domain.ledger import AssetId

logger = logging.getLogger(__name__)
DEFAULT_QUOTE = "USD"


def _parse_requested_timestamp(value: str) -> datetime:
    try:
        parsed_date = date.fromisoformat(value)
    except ValueError:
        parsed_date = None

    if parsed_date is not None:
        return datetime.combine(parsed_date, time.min, tzinfo=timezone.utc)

    try:
        parsed_datetime = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "timestamp must be ISO formatted, e.g. 2026-01-01 or 2026-01-01T23:34+00:00"
        ) from exc

    if parsed_datetime.tzinfo is None:
        return parsed_datetime.replace(tzinfo=timezone.utc)
    return parsed_datetime.astimezone(timezone.utc)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch one CoinMarketCap historical quote for a token at an ISO date or datetime."
    )
    parser.add_argument("token", help="Token/base asset symbol, e.g. ETH, BTC, SOL.")
    parser.add_argument(
        "--timestamp",
        type=_parse_requested_timestamp,
        default=datetime.now(timezone.utc) - timedelta(hours=1),
        help="ISO date or datetime. Date-only values are interpreted as T00:00:00Z. Defaults to one hour ago (UTC).",
    )
    parser.add_argument("--quote", default=DEFAULT_QUOTE, help=f"Quote asset symbol (default: {DEFAULT_QUOTE}).")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    client = CoinMarketCapClient(
        api_key=config().coinmarketcap_api_key,
        high_resolution_days=config().coinmarketcap_high_resolution_days,
    )
    record = client.fetch_record(AssetId(args.token), AssetId(args.quote), timestamp=args.timestamp)
    payload = {
        "requested_timestamp": args.timestamp.isoformat(),
        "base": record.base_id,
        "quote": record.quote_id,
        "rate": str(record.rate) if record.rate is not None else None,
        "valid_from": record.valid_from.isoformat(),
        "valid_to": record.valid_to.isoformat(),
        "source": record.source,
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    main()
