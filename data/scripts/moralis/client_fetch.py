# flake8: noqa: E402 Module level import not at top of file
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from utils import _parse_print_count

SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from clients.moralis import MoralisClient
from config import config
from domain.ledger import EventLocation, WalletAddress


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch wallet history directly from Moralis API.")
    parser.add_argument(
        "--location",
        required=True,
        help="Location name, e.g. ethereum, arbitrum, optimism, base.",
    )
    parser.add_argument("--address", required=True, help="Wallet address to query.")
    parser.add_argument(
        "--from-date",
        type=_parse_date,
        default=None,
        help="Optional start date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=1.0,
        help="Delay between Moralis pagination requests (default: 1.0).",
    )
    parser.add_argument(
        "--print-count",
        type=_parse_print_count,
        default=3,
        help="Number of transactions to print (default: 3). Use 'all' to print every returned transaction.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    client = MoralisClient(api_key=config().moralis_api_key, delay_seconds=args.delay_seconds)
    transactions = client.fetch_transactions(
        location=EventLocation(args.location.strip().upper()),
        address=WalletAddress(args.address.lower()),
        from_date=args.from_date,
    )
    total_count = len(transactions)
    if args.print_count is None:
        printed_transactions = transactions
    else:
        printed_transactions = transactions[: args.print_count]
    printed_count = len(printed_transactions)

    print(json.dumps(printed_transactions, indent=2, default=str))
    print(f"Printed {printed_count} transactions out of {total_count} returned.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    main()
