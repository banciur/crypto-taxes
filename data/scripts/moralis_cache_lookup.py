# flake8: noqa: E402
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sqlalchemy import select

from db.transactions_cache import CACHE_DB_PATH, MoralisTransactionOrm, init_transactions_cache_db


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lookup Moralis cache records by id or transaction hash.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--id", type=int, help="Record id in moralis_transactions.")
    group.add_argument("--hash", dest="tx_hash", help="Transaction hash to lookup.")
    parser.add_argument(
        "--db",
        type=Path,
        default=CACHE_DB_PATH,
        help="Path to cache DB (default: artifacts/transactions_cache.db).",
    )
    return parser.parse_args(argv)


def _format_record(row: MoralisTransactionOrm) -> dict[str, object]:
    return {
        "id": row.id,
        "chain": row.chain,
        "hash": row.hash,
        "block_number": row.block_number,
        "transaction_index": row.transaction_index,
        "block_timestamp": row.block_timestamp.isoformat(),
        "payload": json.loads(row.payload),
    }


def _print_json(data: object) -> None:
    print(json.dumps(data, indent=2))


def _lookup_by_id(session, record_id: int) -> None:
    stmt = select(MoralisTransactionOrm).where(MoralisTransactionOrm.id == record_id)
    row = session.execute(stmt).scalar_one_or_none()
    if row is None:
        print(f"No Moralis cache record found for id={record_id}.")
        return
    _print_json(_format_record(row))


def _lookup_by_hash(session, tx_hash: str) -> None:
    stmt = select(MoralisTransactionOrm).where(MoralisTransactionOrm.hash == tx_hash)
    rows = session.execute(stmt).scalars().all()
    if not rows:
        print(f"No Moralis cache records found for hash={tx_hash}.")
        return
    records = [_format_record(row) for row in rows]
    _print_json(records[0] if len(records) == 1 else records)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    session = init_transactions_cache_db(db_file=args.db)
    if args.id is not None:
        _lookup_by_id(session, args.id)
    else:
        _lookup_by_hash(session, args.tx_hash)


if __name__ == "__main__":
    main()
