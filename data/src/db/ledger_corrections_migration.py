from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from db.corrections_common import init_corrections_db
from db.ledger_corrections import (
    LedgerCorrectionLegOrm,
    LedgerCorrectionOrm,
    LedgerCorrectionSourceOrm,
)


def migrate_legacy_corrections(*, main_db_path: Path, corrections_db_path: Path) -> None:
    corrections_session = init_corrections_db(db_path=corrections_db_path, reset=False)
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


def _migrate_legacy_corrections(*, main_session: Session, corrections_session: Session) -> None:
    existing = corrections_session.execute(select(LedgerCorrectionOrm.id).limit(1)).scalar_one_or_none()
    if existing is not None:
        raise RuntimeError("ledger_corrections already contains data; refusing to run migration twice")

    for row in corrections_session.execute(
        text(
            """
            SELECT id, origin_location, origin_external_id, is_deleted
            FROM spam_corrections
            ORDER BY origin_location, origin_external_id
            """
        )
    ).mappings():
        timestamp = _exact_raw_timestamp(
            main_session=main_session,
            origin_location=row["origin_location"],
            origin_external_id=row["origin_external_id"],
        )
        is_deleted = bool(row["is_deleted"])
        correction = LedgerCorrectionOrm(
            id=UUID(row["id"]),
            timestamp=timestamp,
            price_per_token=None,
            note="",
            is_deleted=is_deleted,
        )
        correction.sources = [
            LedgerCorrectionSourceOrm(
                origin_location=row["origin_location"],
                origin_external_id=row["origin_external_id"],
                is_deleted=is_deleted,
            )
        ]
        corrections_session.add(correction)

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
        correction = LedgerCorrectionOrm(
            id=UUID(row["id"]),
            timestamp=datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")),
            price_per_token=None,
            note="",
            is_deleted=False,
        )
        correction.sources = [
            LedgerCorrectionSourceOrm(
                origin_location=source_row["origin_location"],
                origin_external_id=source_row["origin_external_id"],
                is_deleted=False,
            )
            for source_row in corrections_session.execute(
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
        ]
        correction.legs = [
            LedgerCorrectionLegOrm(
                id=UUID(leg_row["id"]),
                asset_id=leg_row["asset_id"],
                quantity=leg_row["quantity"],
                account_chain_id=leg_row["account_chain_id"],
                is_fee=bool(leg_row["is_fee"]),
            )
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
        corrections_session.add(correction)

    corrections_session.commit()


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
