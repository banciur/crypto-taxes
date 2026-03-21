from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from db.corrections_common import init_corrections_db
from db.ledger_corrections import LedgerCorrectionRepository
from db.ledger_corrections_migration import migrate_legacy_corrections
from db.models import Base
from domain.ledger import EventLocation


def _create_legacy_tables(corrections_db_path: Path) -> None:
    engine = create_engine(f"sqlite:///{corrections_db_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE spam_corrections (
                    id TEXT PRIMARY KEY,
                    origin_location TEXT NOT NULL,
                    origin_external_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    is_deleted INTEGER NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE replacement_corrections (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE replacement_correction_sources (
                    replacement_correction_id TEXT NOT NULL,
                    origin_location TEXT NOT NULL,
                    origin_external_id TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE replacement_correction_legs (
                    id TEXT PRIMARY KEY,
                    replacement_correction_id TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    account_chain_id TEXT NOT NULL,
                    is_fee INTEGER NOT NULL
                )
                """
            )
        )
    engine.dispose()


def _create_main_db(main_db_path: Path) -> None:
    engine = create_engine(f"sqlite:///{main_db_path}")
    Base.metadata.create_all(engine)
    engine.dispose()


def test_migrate_legacy_corrections_carries_forward_active_and_deleted_sources(tmp_path: Path) -> None:
    main_db_path = tmp_path / "main.db"
    corrections_db_path = tmp_path / "corrections.db"
    _create_main_db(main_db_path)
    _create_legacy_tables(corrections_db_path)

    main_engine = create_engine(f"sqlite:///{main_db_path}")
    with main_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO ledger_events (
                    id, timestamp, ingestion, origin_location, origin_external_id
                ) VALUES (
                    :id, :timestamp, 'raw', :origin_location, :origin_external_id
                )
                """
            ),
            [
                {
                    "id": str(uuid4()),
                    "timestamp": "2024-02-01T10:00:00Z",
                    "origin_location": EventLocation.ARBITRUM.value,
                    "origin_external_id": "0xactive",
                },
                {
                    "id": str(uuid4()),
                    "timestamp": "2024-02-01T11:00:00Z",
                    "origin_location": EventLocation.ARBITRUM.value,
                    "origin_external_id": "0xtombstone",
                },
            ],
        )

    corrections_engine = create_engine(f"sqlite:///{corrections_db_path}")
    with corrections_engine.begin() as connection:
        active_spam_id = str(uuid4())
        deleted_spam_id = str(uuid4())
        replacement_id = str(uuid4())
        leg_id = str(uuid4())
        connection.execute(
            text(
                """
                INSERT INTO spam_corrections (
                    id, origin_location, origin_external_id, source, is_deleted
                ) VALUES
                    (:active_id, :location, '0xactive', 'MANUAL', 0),
                    (:deleted_id, :location, '0xtombstone', 'MANUAL', 1)
                """
            ),
            {
                "active_id": active_spam_id,
                "deleted_id": deleted_spam_id,
                "location": EventLocation.ARBITRUM.value,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO replacement_corrections (id, timestamp)
                VALUES (:id, '2024-02-02T12:00:00Z')
                """
            ),
            {"id": replacement_id},
        )
        connection.execute(
            text(
                """
                INSERT INTO replacement_correction_sources (
                    replacement_correction_id, origin_location, origin_external_id
                ) VALUES (:id, :location, '0xreplace')
                """
            ),
            {"id": replacement_id, "location": EventLocation.ETHEREUM.value},
        )
        connection.execute(
            text(
                """
                INSERT INTO replacement_correction_legs (
                    id, replacement_correction_id, asset_id, quantity, account_chain_id, is_fee
                ) VALUES (:leg_id, :correction_id, 'BTC', '1', 'wallet', 0)
                """
            ),
            {"leg_id": leg_id, "correction_id": replacement_id},
        )
    corrections_engine.dispose()
    main_engine.dispose()

    migrate_legacy_corrections(main_db_path=main_db_path, corrections_db_path=corrections_db_path)

    corrections_session = init_corrections_db(db_path=corrections_db_path, reset=False)
    repo = LedgerCorrectionRepository(corrections_session)
    corrections = repo.list()

    assert len(corrections) == 2
    correction_ids = {str(correction.id) for correction in corrections}
    assert correction_ids == {active_spam_id, replacement_id}
    active_spam = next(correction for correction in corrections if str(correction.id) == active_spam_id)
    replacement = next(correction for correction in corrections if str(correction.id) == replacement_id)
    assert active_spam.timestamp == datetime(2024, 2, 1, 10, 0, tzinfo=timezone.utc)
    assert replacement.sources[0].external_id == "0xreplace"
    assert (
        repo.has_source(
            event_origin=active_spam.sources[0],
            include_deleted=False,
        )
        is True
    )
    assert (
        repo.has_source(
            event_origin=type(active_spam.sources[0])(
                location=EventLocation.ARBITRUM,
                external_id="0xtombstone",
            ),
            include_deleted=True,
        )
        is True
    )


def test_migrate_legacy_corrections_fails_when_spam_source_is_missing(tmp_path: Path) -> None:
    main_db_path = tmp_path / "main.db"
    corrections_db_path = tmp_path / "corrections.db"
    _create_main_db(main_db_path)
    _create_legacy_tables(corrections_db_path)

    corrections_engine = create_engine(f"sqlite:///{corrections_db_path}")
    with corrections_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO spam_corrections (
                    id, origin_location, origin_external_id, source, is_deleted
                ) VALUES (:id, :location, '0xmissing', 'MANUAL', 0)
                """
            ),
            {"id": str(uuid4()), "location": EventLocation.ARBITRUM.value},
        )
    corrections_engine.dispose()

    with pytest.raises(
        RuntimeError,
        match="Spam/discard migration requires exactly one matching raw event: ARBITRUM/0xmissing",
    ):
        migrate_legacy_corrections(main_db_path=main_db_path, corrections_db_path=corrections_db_path)
