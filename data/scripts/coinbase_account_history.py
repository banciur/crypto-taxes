# flake8: noqa: E402
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Sequence

from utils import _parse_print_count

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from clients.coinbase import CoinbaseClient
from config import config


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Coinbase account transaction history from Track API.")
    parser.add_argument(
        "--print-count",
        type=_parse_print_count,
        default=3,
        help="Number of transactions to print (default: 3). Use 'all' to print every returned transaction.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    client = CoinbaseClient(
        api_key=config().coinbase_key_name,
        api_secret=config().coinbase_key_prv,
    )

    transactions = client.fetch_transactions()
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
