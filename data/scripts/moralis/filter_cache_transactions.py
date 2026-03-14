# flake8: noqa: E402
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sqlalchemy import select

from config import TRANSACTIONS_CACHE_DB_PATH
from db.tx_cache_common import init_transactions_cache_db
from db.tx_cache_moralis import MoralisTransactionOrm


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print cached Moralis transactions with non-zero value or non-empty native_transfers."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=TRANSACTIONS_CACHE_DB_PATH,
        help="Path to cache DB (default: artifacts/transactions_cache.db).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max number of matching transactions to print.",
    )
    return parser.parse_args(argv)


def _has_non_zero_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and value.strip() == "":
        return False
    try:
        return Decimal(str(value)) != 0
    except (InvalidOperation, ValueError):
        return False


def _has_native_transfers(native_transfers: Any) -> bool:
    return isinstance(native_transfers, list) and len(native_transfers) > 0


def _matching_transactions(session) -> list[dict[str, object]]:
    stmt = select(MoralisTransactionOrm).order_by(
        MoralisTransactionOrm.block_timestamp,
        MoralisTransactionOrm.block_number,
        MoralisTransactionOrm.transaction_index,
    )
    rows = session.execute(stmt).scalars().all()
    matches: list[dict[str, object]] = []
    for row in rows:
        payload = json.loads(row.payload)
        if not (_has_non_zero_value(payload.get("value")) or _has_native_transfers(payload.get("native_transfers"))):
            continue
        payload["location"] = row.location
        matches.append(payload)
    return matches


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    session = init_transactions_cache_db(db_path=args.db)
    matches = _matching_transactions(session)
    if args.limit is not None:
        matches = matches[: args.limit]
    print(json.dumps(matches, indent=2, default=str))


if __name__ == "__main__":
    main()
