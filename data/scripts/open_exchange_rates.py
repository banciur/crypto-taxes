# flake8: noqa: E402
import argparse
import json
import logging
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from clients.open_exchange_rates import OpenExchangeRatesClient
from domain.ledger import AssetId
from domain.pricing import PriceRecord

logger = logging.getLogger(__name__)
DEFAULT_BASE = "EUR"
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


def _serialize_quote(quote: PriceRecord) -> dict[str, Any]:
    return {
        "base_id": quote.base_id,
        "quote_id": quote.quote_id,
        "rate": str(quote.rate),
        "source": quote.source,
        "valid_from": quote.valid_from.isoformat(),
        "valid_to": quote.valid_to.isoformat(),
        "fetched_at": quote.fetched_at.isoformat(),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch one Open Exchange Rates historical cross rate for a currency pair."
    )
    parser.add_argument(
        "base",
        nargs="?",
        default=DEFAULT_BASE,
        help=f"Base currency symbol (default: {DEFAULT_BASE}).",
    )
    parser.add_argument(
        "quote",
        nargs="?",
        default=DEFAULT_QUOTE,
        help=f"Quote currency symbol (default: {DEFAULT_QUOTE}).",
    )
    parser.add_argument(
        "--timestamp",
        type=_parse_requested_timestamp,
        default=datetime.now(timezone.utc) - timedelta(hours=1),
        help="ISO date or datetime. Date-only values are interpreted as T00:00:00Z. Defaults to one hour ago (UTC).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the JSON payload. Defaults to stdout.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    quote = OpenExchangeRatesClient().fetch_record(
        AssetId(args.base),
        AssetId(args.quote),
        timestamp=args.timestamp,
    )

    if quote is None:
        raise SystemExit(
            f"No Open Exchange Rates rate available for {args.base.upper()}->{args.quote.upper()} "
            f"at {args.timestamp.isoformat()}"
        )

    payload = {
        "requested_timestamp": args.timestamp.isoformat(),
        "base": args.base.upper(),
        "quote": args.quote.upper(),
        "rate": _serialize_quote(quote),
    }
    rendered = json.dumps(payload, indent=2)

    if args.output is None:
        print(rendered)
        return

    args.output.write_text(rendered + "\n")
    logger.info(
        "Wrote %s->%s rate at %s to %s",
        args.base.upper(),
        args.quote.upper(),
        args.timestamp.isoformat(),
        args.output,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    main()
