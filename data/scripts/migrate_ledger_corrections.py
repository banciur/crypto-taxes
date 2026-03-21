# This should not be a part of the final merge of PR. This is a one-off operation and will be removed after migration is complete
# ruff: noqa: E402
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence
from uuid import UUID

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from config import CORRECTIONS_DB_PATH, DB_PATH
from db.ledger_corrections import CorrectionsBase, LedgerCorrectionOrm, LedgerCorrectionSourceOrm
from db.session import init_db_session


def migrate_legacy_corrections(*, main_db_path: Path, corrections_db_path: Path) -> None:
    corrections_session = init_db_session(
        db_path=corrections_db_path,
        metadata=CorrectionsBase.metadata,
        reset=False,
    )
    main_engine = create_engine(f"sqlite:///{main_db_path}")
    main_session = sessionmaker(main_engine)()
    try:
        _migrate_legacy_corrections(
            main_session=main_session,
            corrections_session=corrections_session,
        )
    finally:
        main_session.close()
        main_engine.dispose()
        corrections_session.close()


def _origin_key(*, location: str, external_id: str) -> tuple[str, str]:
    return (location, external_id)


def _format_origin_key(origin_key: tuple[str, str]) -> str:
    location, external_id = origin_key
    return f"{location}/{external_id}"


def _default_note_value(corrections_session: Session) -> str | None:
    note_column = next(
        row
        for row in corrections_session.execute(text("PRAGMA table_info('ledger_corrections')")).mappings()
        if row["name"] == "note"
    )
    return "" if bool(note_column["notnull"]) else None


def _table_columns(corrections_session: Session, table_name: str) -> set[str]:
    return {row["name"] for row in corrections_session.execute(text(f"PRAGMA table_info('{table_name}')")).mappings()}


def _sqlite_uuid(value: UUID) -> str:
    return value.hex


def _insert_correction_row(
    *,
    corrections_session: Session,
    correction_id: UUID,
    timestamp: datetime,
    price_per_token: str | None,
    note: str | None,
    is_deleted: bool,
) -> None:
    corrections_session.execute(
        text(
            """
            INSERT INTO ledger_corrections (id, timestamp, price_per_token, note, is_deleted)
            VALUES (:id, :timestamp, :price_per_token, :note, :is_deleted)
            """
        ),
        {
            "id": _sqlite_uuid(correction_id),
            "timestamp": timestamp,
            "price_per_token": price_per_token,
            "note": note,
            "is_deleted": is_deleted,
        },
    )


def _insert_source_rows(
    *,
    corrections_session: Session,
    correction_id: UUID,
    source_rows: list[dict[str, str]],
    source_table_columns: set[str],
) -> None:
    parameters = [
        {
            "correction_id": _sqlite_uuid(correction_id),
            "origin_location": source_row["origin_location"],
            "origin_external_id": source_row["origin_external_id"],
            "is_deleted": False,
        }
        for source_row in source_rows
    ]
    if "is_deleted" in source_table_columns:
        corrections_session.execute(
            text(
                """
                INSERT INTO ledger_correction_sources (
                    correction_id, origin_location, origin_external_id, is_deleted
                ) VALUES (
                    :correction_id, :origin_location, :origin_external_id, :is_deleted
                )
                """
            ),
            parameters,
        )
        return

    corrections_session.execute(
        text(
            """
            INSERT INTO ledger_correction_sources (
                correction_id, origin_location, origin_external_id
            ) VALUES (
                :correction_id, :origin_location, :origin_external_id
            )
            """
        ),
        parameters,
    )


def _insert_leg_rows(
    *,
    corrections_session: Session,
    correction_id: UUID,
    leg_rows: list[dict[str, str | int]],
) -> None:
    if not leg_rows:
        return

    corrections_session.execute(
        text(
            """
            INSERT INTO ledger_correction_legs (
                id, correction_id, asset_id, quantity, account_chain_id, is_fee
            ) VALUES (
                :id, :correction_id, :asset_id, :quantity, :account_chain_id, :is_fee
            )
            """
        ),
        [
            {
                "id": leg_row["id"],
                "correction_id": _sqlite_uuid(correction_id),
                "asset_id": leg_row["asset_id"],
                "quantity": leg_row["quantity"],
                "account_chain_id": leg_row["account_chain_id"],
                "is_fee": leg_row["is_fee"],
            }
            for leg_row in leg_rows
        ],
    )


def _table_exists(session: Session, table_name: str) -> bool:
    return (
        session.execute(
            text(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table' AND name = :table_name
                """
            ),
            {"table_name": table_name},
        ).scalar_one_or_none()
        is not None
    )


def _migrate_legacy_corrections(*, main_session: Session, corrections_session: Session) -> None:
    default_note = _default_note_value(corrections_session)
    source_table_columns = _table_columns(corrections_session, "ledger_correction_sources")
    existing_correction_ids = set(corrections_session.execute(select(LedgerCorrectionOrm.id)).scalars())
    existing_source_keys = {
        _origin_key(location=location, external_id=external_id)
        for location, external_id in corrections_session.execute(
            select(
                LedgerCorrectionSourceOrm.origin_location,
                LedgerCorrectionSourceOrm.origin_external_id,
            )
        )
    }

    if _table_exists(corrections_session, "spam_corrections"):
        for row in corrections_session.execute(
            text(
                """
                SELECT id, origin_location, origin_external_id, is_deleted
                FROM spam_corrections
                ORDER BY origin_location, origin_external_id
                """
            )
        ).mappings():
            correction_id = UUID(row["id"])
            source_key = _origin_key(
                location=row["origin_location"],
                external_id=row["origin_external_id"],
            )
            if source_key in existing_source_keys:
                continue
            if correction_id in existing_correction_ids:
                raise RuntimeError(f"Correction id already exists in unified corrections: {correction_id}")

            timestamp = _exact_raw_timestamp(
                main_session=main_session,
                origin_location=row["origin_location"],
                origin_external_id=row["origin_external_id"],
            )
            is_deleted = bool(row["is_deleted"])
            _insert_correction_row(
                corrections_session=corrections_session,
                correction_id=correction_id,
                timestamp=timestamp,
                price_per_token=None,
                note=default_note,
                is_deleted=is_deleted,
            )
            _insert_source_rows(
                corrections_session=corrections_session,
                correction_id=correction_id,
                source_rows=[
                    {
                        "origin_location": row["origin_location"],
                        "origin_external_id": row["origin_external_id"],
                    }
                ],
                source_table_columns=source_table_columns,
            )
            existing_correction_ids.add(correction_id)
            existing_source_keys.add(source_key)

    if _table_exists(corrections_session, "replacement_corrections"):
        replacement_rows = corrections_session.execute(
            text(
                """
                SELECT id, timestamp
                FROM replacement_corrections
                ORDER BY timestamp, id
                """
            )
        ).mappings()
        for row in replacement_rows:
            correction_id = UUID(row["id"])
            if correction_id in existing_correction_ids:
                continue

            source_rows = list(
                corrections_session.execute(
                    text(
                        """
                        SELECT origin_location, origin_external_id
                        FROM replacement_correction_sources
                        WHERE replacement_correction_id = :correction_id
                        ORDER BY origin_location, origin_external_id
                        """
                    ),
                    {"correction_id": row["id"]},
                ).mappings()
            )
            conflicting_source_keys = [
                _origin_key(
                    location=source_row["origin_location"],
                    external_id=source_row["origin_external_id"],
                )
                for source_row in source_rows
                if _origin_key(
                    location=source_row["origin_location"],
                    external_id=source_row["origin_external_id"],
                )
                in existing_source_keys
            ]
            if conflicting_source_keys:
                formatted_origins = ", ".join(
                    _format_origin_key(origin_key) for origin_key in sorted(set(conflicting_source_keys))
                )
                raise RuntimeError(
                    f"Replacement migration source already claimed in unified corrections: {formatted_origins}"
                )

            leg_rows = [
                {
                    "id": UUID(leg_row["id"]).hex,
                    "asset_id": leg_row["asset_id"],
                    "quantity": leg_row["quantity"],
                    "account_chain_id": leg_row["account_chain_id"],
                    "is_fee": bool(leg_row["is_fee"]),
                }
                for leg_row in corrections_session.execute(
                    text(
                        """
                        SELECT id, asset_id, quantity, account_chain_id, is_fee
                        FROM replacement_correction_legs
                        WHERE replacement_correction_id = :correction_id
                        ORDER BY id
                        """
                    ),
                    {"correction_id": row["id"]},
                ).mappings()
            ]
            _insert_correction_row(
                corrections_session=corrections_session,
                correction_id=correction_id,
                timestamp=datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")),
                price_per_token=None,
                note=default_note,
                is_deleted=False,
            )
            _insert_source_rows(
                corrections_session=corrections_session,
                correction_id=correction_id,
                source_rows=[
                    {
                        "origin_location": source_row["origin_location"],
                        "origin_external_id": source_row["origin_external_id"],
                    }
                    for source_row in source_rows
                ],
                source_table_columns=source_table_columns,
            )
            _insert_leg_rows(
                corrections_session=corrections_session,
                correction_id=correction_id,
                leg_rows=leg_rows,
            )
            existing_correction_ids.add(correction_id)
            existing_source_keys.update(
                _origin_key(
                    location=source_row["origin_location"],
                    external_id=source_row["origin_external_id"],
                )
                for source_row in source_rows
            )

    if _table_exists(main_session, "seed_events") and _table_exists(main_session, "seed_event_legs"):
        _migrate_seed_events(
            main_session=main_session,
            corrections_session=corrections_session,
            existing_correction_ids=existing_correction_ids,
            default_note=default_note,
        )

    corrections_session.commit()


def _migrate_seed_events(
    *,
    main_session: Session,
    corrections_session: Session,
    existing_correction_ids: set[UUID],
    default_note: str | None,
) -> None:
    for row in main_session.execute(
        text(
            """
            SELECT id, timestamp, price_per_token
            FROM seed_events
            ORDER BY timestamp, id
            """
        )
    ).mappings():
        correction_id = UUID(row["id"])
        if correction_id in existing_correction_ids:
            continue

        leg_rows = [
            {
                "id": UUID(leg_row["id"]).hex,
                "asset_id": leg_row["asset_id"],
                "quantity": leg_row["quantity"],
                "account_chain_id": leg_row["account_chain_id"],
                "is_fee": bool(leg_row["is_fee"]),
            }
            for leg_row in main_session.execute(
                text(
                    """
                    SELECT id, asset_id, quantity, account_chain_id, is_fee
                    FROM seed_event_legs
                    WHERE event_id = :event_id
                    ORDER BY id
                    """
                ),
                {"event_id": row["id"]},
            ).mappings()
        ]
        if len(leg_rows) != 1:
            raise RuntimeError(f"Seed/opening-balance migration requires exactly one leg: {row['id']}")

        _insert_correction_row(
            corrections_session=corrections_session,
            correction_id=correction_id,
            timestamp=datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")),
            price_per_token=row["price_per_token"],
            note=default_note,
            is_deleted=False,
        )
        _insert_leg_rows(
            corrections_session=corrections_session,
            correction_id=correction_id,
            leg_rows=leg_rows,
        )
        existing_correction_ids.add(correction_id)


def _exact_raw_timestamp(
    *,
    main_session: Session,
    origin_location: str,
    origin_external_id: str,
) -> datetime:
    rows = (
        main_session.execute(
            text(
                """
            SELECT timestamp
            FROM ledger_events
            WHERE origin_location = :origin_location
              AND origin_external_id = :origin_external_id
            """
            ),
            {
                "origin_location": origin_location,
                "origin_external_id": origin_external_id,
            },
        )
        .scalars()
        .all()
    )
    if len(rows) != 1:
        raise RuntimeError(
            f"Spam/discard migration requires exactly one matching raw event: {origin_location}/{origin_external_id}"
        )
    return datetime.fromisoformat(rows[0].replace("Z", "+00:00"))


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Migrate legacy spam/replacement corrections into ledger_corrections.")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--corrections-db", type=Path, default=CORRECTIONS_DB_PATH)
    args = parser.parse_args(argv)
    migrate_legacy_corrections(main_db_path=args.db, corrections_db_path=args.corrections_db)


if __name__ == "__main__":
    main()
