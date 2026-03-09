# flake8: noqa: E402
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from clients.coinbase import CoinbaseClient
from config import config


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch account balances from Coinbase Advanced Trade.")
    parser.add_argument(
        "--include-zero-balances",
        action="store_true",
        help="Include zero balances in output.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    balances = CoinbaseClient(
        api_key=config().coinbase_key_name,
        api_secret=config().coinbase_key_prv,
    ).fetch_balances(include_zero_balances=args.include_zero_balances)

    if not balances:
        print("No balances returned.")
        return

    print("currency,balance,account_name,account_uuid")
    for balance in balances:
        print(f"{balance.currency},{balance.value},{balance.account_name},{balance.account_uuid}")
    print(f"Returned {len(balances)} balances.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    main()
