# flake8: noqa: E402
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from clients.moralis import SyncMode, build_default_service


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch wallet history via Moralis and cache results.")
    parser.add_argument(
        "--accounts",
        type=Path,
        default=Path("data/accounts.json"),
        help="Path to accounts JSON (default: data/accounts.json)",
    )
    parser.add_argument(
        "--mode",
        type=SyncMode,
        choices=list(SyncMode),
        default=SyncMode.BUDGET,
        help="Sync mode: fresh hits API each time; budget uses cache when possible (default: budget).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    service = build_default_service(accounts_path=args.accounts)
    transactions = service.get_transactions(args.mode)
    print(f"Synced {len(transactions)} transactions (cached in DB).")
    preview = transactions[-5:] if len(transactions) >= 5 else transactions
    if preview:
        print("Last 5 transactions:")
        for tx in preview:
            print(json.dumps(tx, indent=2))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    main()
