# flake8: noqa: E402
import argparse
import json
import logging
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from clients.coindesk import CoinDeskClient, SpotInstrumentOHLC, fetch_spot_candle

logger = logging.getLogger(__name__)
DEFAULT_QUOTE = "EUR"
DEFAULT_MARKET = "coinbase"
DEFAULT_AGGREGATE_MINUTES = 60


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


def _serialize_entry(entry: SpotInstrumentOHLC) -> dict[str, Any]:
    return {
        "timestamp": entry.timestamp.isoformat(),
        "market": entry.market,
        "instrument": entry.instrument,
        "mapped_instrument": entry.mapped_instrument,
        "base_asset": entry.base_asset,
        "quote_asset": entry.quote_asset,
        "open": str(entry.open) if entry.open is not None else None,
        "high": str(entry.high) if entry.high is not None else None,
        "low": str(entry.low) if entry.low is not None else None,
        "close": str(entry.close),
        "volume": str(entry.volume) if entry.volume is not None else None,
        "quote_volume": str(entry.quote_volume) if entry.quote_volume is not None else None,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch one CoinDesk spot price bucket for a token at an ISO date or datetime."
    )
    parser.add_argument(
        "token_positional",
        nargs="?",
        metavar="token",
        help="Token/base asset symbol, e.g. ETH, BTC, SOL. May also be given as --token.",
    )
    parser.add_argument(
        "--token",
        dest="token_option",
        help="Token/base asset symbol (alternative to the positional argument).",
    )
    parser.add_argument(
        "--timestamp",
        type=_parse_requested_timestamp,
        default=datetime.now(timezone.utc) - timedelta(hours=1),
        help="ISO date or datetime. Date-only values are interpreted as T00:00:00Z. Defaults to one hour ago (UTC).",
    )
    parser.add_argument(
        "--quote",
        default=DEFAULT_QUOTE,
        help=f"Quote asset symbol (default: {DEFAULT_QUOTE}).",
    )
    parser.add_argument(
        "--market",
        default=DEFAULT_MARKET,
        help=f"Exchange/market slug for CoinDesk (default: {DEFAULT_MARKET}).",
    )
    parser.add_argument(
        "--aggregate-minutes",
        type=int,
        default=DEFAULT_AGGREGATE_MINUTES,
        help=(
            "Bucket size in minutes. Use 1-30 for minute candles or a multiple of 60 for hour candles "
            f"(default: {DEFAULT_AGGREGATE_MINUTES})."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the JSON payload. Defaults to stdout.",
    )
    args = parser.parse_args(argv)
    token = args.token_positional or args.token_option
    if not token:
        parser.error("token is required (as a positional argument or with --token)")
    args.token = token
    return args


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    instrument = f"{args.token.upper()}-{args.quote.upper()}"
    candle = fetch_spot_candle(
        client=CoinDeskClient(),
        market=args.market,
        instrument=instrument,
        timestamp=args.timestamp,
        aggregate_minutes=args.aggregate_minutes,
    )
    payload = {
        "requested_timestamp": args.timestamp.isoformat(),
        "market": args.market,
        "instrument": instrument,
        "aggregate_minutes": args.aggregate_minutes,
        "candle": _serialize_entry(candle),
    }
    rendered = json.dumps(payload, indent=2)

    if args.output is None:
        print(rendered)
        return

    args.output.write_text(rendered + "\n")
    logger.info("Wrote %s candle at %s to %s", instrument, args.timestamp.isoformat(), args.output)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    main()
