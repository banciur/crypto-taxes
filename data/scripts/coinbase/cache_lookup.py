# This file is completely vibed and I didn't read it.
# flake8: noqa: E402
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence
from uuid import UUID

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sqlalchemy import select

from config import CORRECTIONS_DB_PATH, TRANSACTIONS_CACHE_DB_PATH
from db.ledger_corrections import CorrectionsBase, LedgerCorrectionOrm
from db.session import init_db_session
from db.tx_cache_coinbase import CoinbaseAccountOrm, CoinbaseTransactionOrm
from db.tx_cache_common import init_transactions_cache_db
from utils.misc import ensure_utc_datetime

_NESTED_ID_TYPES = frozenset({"buy", "sell", "trade"})


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lookup Coinbase cache records by Coinbase event external id or correction id."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--external-id",
        help="Coinbase event external id. Supports raw transaction ids, buy/sell/trade ids, and wrap_asset synthetic ids.",
    )
    group.add_argument(
        "--correction-id",
        help="Correction UUID from artifacts/corrections.db.",
    )
    parser.add_argument(
        "--cache-db",
        type=Path,
        default=TRANSACTIONS_CACHE_DB_PATH,
        help="Path to Coinbase cache DB (default: artifacts/transactions_cache.db).",
    )
    parser.add_argument(
        "--corrections-db",
        type=Path,
        default=CORRECTIONS_DB_PATH,
        help="Path to corrections DB (default: artifacts/corrections.db).",
    )
    return parser.parse_args(argv)


def _format_timestamp(value) -> str | None:
    if value is None:
        return None
    return ensure_utc_datetime(value).isoformat()


def _format_transaction(
    row: CoinbaseTransactionOrm,
    *,
    account_by_id: dict[str, CoinbaseAccountOrm],
) -> dict[str, object]:
    account = account_by_id.get(row.account_id)
    return {
        "transaction_id": row.transaction_id,
        "account_id": row.account_id,
        "created_at": _format_timestamp(row.created_at),
        "type": row.type,
        "payload": json.loads(row.payload),
        "account": None if account is None else json.loads(account.payload),
    }


def _format_correction(row: LedgerCorrectionOrm) -> dict[str, object]:
    sources = sorted(
        row.sources,
        key=lambda source: (source.origin_location, source.origin_external_id),
    )
    legs = sorted(row.legs, key=lambda leg: leg.id)
    return {
        "id": str(row.id),
        "timestamp": _format_timestamp(row.timestamp),
        "price_per_token": None if row.price_per_token is None else str(row.price_per_token),
        "note": row.note,
        "sources": [
            {
                "location": source.origin_location,
                "external_id": source.origin_external_id,
            }
            for source in sources
        ],
        "legs": [
            {
                "id": str(leg.id),
                "asset_id": leg.asset_id,
                "quantity": str(leg.quantity),
                "account_chain_id": leg.account_chain_id,
                "is_fee": leg.is_fee,
            }
            for leg in legs
        ],
    }


def _load_account_map(cache_session, account_ids: set[str]) -> dict[str, CoinbaseAccountOrm]:
    if not account_ids:
        return {}
    rows = cache_session.execute(
        select(CoinbaseAccountOrm).where(CoinbaseAccountOrm.account_id.in_(sorted(account_ids)))
    ).scalars()
    return {row.account_id: row for row in rows}


def _wrap_member_ids(external_id: str) -> list[str]:
    if not external_id.startswith("wrap_asset:"):
        return []
    _, _, member_ids = external_id.partition(":")
    return [member_id for member_id in member_ids.split(",") if member_id]


def _matching_rows_for_external_id(cache_session, external_id: str) -> list[CoinbaseTransactionOrm]:
    matches_by_id: dict[str, CoinbaseTransactionOrm] = {}

    direct_matches = cache_session.execute(
        select(CoinbaseTransactionOrm).where(CoinbaseTransactionOrm.transaction_id == external_id)
    ).scalars()
    for row in direct_matches:
        matches_by_id[row.transaction_id] = row

    wrap_member_ids = _wrap_member_ids(external_id)
    if wrap_member_ids:
        wrap_rows = cache_session.execute(
            select(CoinbaseTransactionOrm).where(CoinbaseTransactionOrm.transaction_id.in_(wrap_member_ids))
        ).scalars()
        for row in wrap_rows:
            matches_by_id[row.transaction_id] = row

    nested_rows = cache_session.execute(
        select(CoinbaseTransactionOrm).where(CoinbaseTransactionOrm.type.in_(sorted(_NESTED_ID_TYPES)))
    ).scalars()
    for row in nested_rows:
        payload = json.loads(row.payload)
        nested = payload.get(row.type)
        if isinstance(nested, dict) and nested.get("id") == external_id:
            matches_by_id[row.transaction_id] = row

    return sorted(matches_by_id.values(), key=lambda row: (row.created_at, row.transaction_id))


def _lookup_external_id(cache_session, external_id: str) -> dict[str, object]:
    rows = _matching_rows_for_external_id(cache_session, external_id)
    account_by_id = _load_account_map(cache_session, {row.account_id for row in rows})
    return {
        "external_id": external_id,
        "match_count": len(rows),
        "transactions": [_format_transaction(row, account_by_id=account_by_id) for row in rows],
    }


def _lookup_correction(cache_session, corrections_session, correction_id: str) -> dict[str, object]:
    correction_uuid = UUID(correction_id)
    correction = (
        corrections_session.execute(select(LedgerCorrectionOrm).where(LedgerCorrectionOrm.id == correction_uuid))
        .unique()
        .scalar_one_or_none()
    )
    if correction is None:
        return {
            "correction_id": str(correction_uuid),
            "found": False,
            "message": f"No correction found for id={correction_uuid}.",
        }

    coinbase_sources = [
        source.origin_external_id for source in correction.sources if source.origin_location == "COINBASE"
    ]
    looked_up_sources = [_lookup_external_id(cache_session, external_id) for external_id in sorted(coinbase_sources)]

    return {
        "correction": _format_correction(correction),
        "coinbase_source_count": len(looked_up_sources),
        "coinbase_sources": looked_up_sources,
    }


def _print_json(data: object) -> None:
    print(json.dumps(data, indent=2))


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    cache_session = init_transactions_cache_db(db_path=args.cache_db)
    corrections_session = init_db_session(
        db_path=args.corrections_db,
        metadata=CorrectionsBase.metadata,
    )
    try:
        if args.external_id is not None:
            _print_json(_lookup_external_id(cache_session, args.external_id))
            return
        _print_json(_lookup_correction(cache_session, corrections_session, args.correction_id))
    finally:
        cache_session.close()
        corrections_session.close()


if __name__ == "__main__":
    main()
