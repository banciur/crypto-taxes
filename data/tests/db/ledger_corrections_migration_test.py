# This should not be a part of the final merge of PR. This is a one-off operation and will be removed after migration is complete
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text

from db.ledger_corrections import (
    CorrectionsBase,
    LedgerCorrectionOrm,
    LedgerCorrectionRepository,
    LedgerCorrectionSourceOrm,
)
from db.models import Base
from db.session import init_db_session
from domain.ledger import EventLocation
from scripts.migrate_ledger_corrections import migrate_legacy_corrections


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


def _create_old_unified_tables(corrections_db_path: Path) -> None:
    engine = create_engine(f"sqlite:///{corrections_db_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE ledger_corrections (
                    id CHAR(32) PRIMARY KEY,
                    timestamp DATETIME NOT NULL,
                    price_per_token VARCHAR,
                    note VARCHAR NOT NULL,
                    is_deleted BOOLEAN NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE ledger_correction_sources (
                    correction_id CHAR(32) NOT NULL,
                    origin_location VARCHAR NOT NULL,
                    origin_external_id VARCHAR NOT NULL,
                    is_deleted BOOLEAN NOT NULL,
                    PRIMARY KEY (correction_id, origin_location, origin_external_id),
                    FOREIGN KEY(correction_id) REFERENCES ledger_corrections (id)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE INDEX ix_ledger_correction_sources_origin
                ON ledger_correction_sources (origin_location, origin_external_id)
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE UNIQUE INDEX uq_ledger_correction_sources_active_origin
                ON ledger_correction_sources (origin_location, origin_external_id)
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE ledger_correction_legs (
                    id CHAR(32) PRIMARY KEY,
                    correction_id CHAR(32) NOT NULL,
                    asset_id VARCHAR NOT NULL,
                    quantity VARCHAR NOT NULL,
                    account_chain_id VARCHAR NOT NULL,
                    is_fee BOOLEAN NOT NULL,
                    FOREIGN KEY(correction_id) REFERENCES ledger_corrections (id)
                )
                """
            )
        )
    engine.dispose()


def _create_main_db(main_db_path: Path) -> None:
    engine = create_engine(f"sqlite:///{main_db_path}")
    Base.metadata.create_all(engine)
    engine.dispose()


def _create_seed_tables(main_db_path: Path) -> None:
    engine = create_engine(f"sqlite:///{main_db_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE seed_events (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    price_per_token TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE seed_event_legs (
                    id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    account_chain_id TEXT NOT NULL,
                    is_fee INTEGER NOT NULL
                )
                """
            )
        )
    engine.dispose()


def test_migrate_legacy_corrections_carries_forward_active_and_deleted_sources(tmp_path: Path) -> None:
    main_db_path = tmp_path / "main.db"
    corrections_db_path = tmp_path / "corrections.db"
    _create_main_db(main_db_path)
    _create_legacy_tables(corrections_db_path)
    corrections_session = init_db_session(
        db_path=corrections_db_path,
        metadata=CorrectionsBase.metadata,
        reset=False,
    )
    existing_spam_id = str(uuid4())
    corrections_session.add(
        LedgerCorrectionOrm(
            id=UUID(existing_spam_id),
            timestamp=datetime(2024, 2, 1, 10, 0, tzinfo=timezone.utc),
            price_per_token=None,
            note=None,
            is_deleted=False,
            sources=[
                LedgerCorrectionSourceOrm(
                    origin_location=EventLocation.ARBITRUM.value,
                    origin_external_id="0xactive",
                )
            ],
        )
    )
    corrections_session.commit()
    corrections_session.close()

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

    corrections_session = init_db_session(
        db_path=corrections_db_path,
        metadata=CorrectionsBase.metadata,
        reset=False,
    )
    repo = LedgerCorrectionRepository(corrections_session)
    corrections = repo.list()

    assert len(corrections) == 2
    correction_ids = {str(correction.id) for correction in corrections}
    assert correction_ids == {existing_spam_id, replacement_id}
    active_spam = next(correction for correction in corrections if str(correction.id) == existing_spam_id)
    replacement = next(correction for correction in corrections if str(correction.id) == replacement_id)
    assert active_spam.timestamp == datetime(2024, 2, 1, 10, 0, tzinfo=timezone.utc)
    replacement_source = next(iter(replacement.sources))
    active_spam_source = next(iter(active_spam.sources))
    assert replacement_source.external_id == "0xreplace"
    assert (
        repo.has_source(
            event_origin=active_spam_source,
            include_deleted=False,
        )
        is True
    )
    assert (
        repo.has_source(
            event_origin=type(active_spam_source)(
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


def test_migrate_legacy_corrections_fails_when_replacement_source_is_already_claimed(
    tmp_path: Path,
) -> None:
    main_db_path = tmp_path / "main.db"
    corrections_db_path = tmp_path / "corrections.db"
    _create_main_db(main_db_path)
    _create_legacy_tables(corrections_db_path)
    corrections_session = init_db_session(
        db_path=corrections_db_path,
        metadata=CorrectionsBase.metadata,
        reset=False,
    )
    corrections_session.add(
        LedgerCorrectionOrm(
            id=uuid4(),
            timestamp=datetime(2024, 2, 1, 9, 0, tzinfo=timezone.utc),
            price_per_token=None,
            note=None,
            is_deleted=False,
            sources=[
                LedgerCorrectionSourceOrm(
                    origin_location=EventLocation.ETHEREUM.value,
                    origin_external_id="0xshared",
                )
            ],
        )
    )
    corrections_session.commit()
    corrections_session.close()

    corrections_engine = create_engine(f"sqlite:///{corrections_db_path}")
    with corrections_engine.begin() as connection:
        replacement_id = str(uuid4())
        leg_id = str(uuid4())
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
                ) VALUES (:id, :location, '0xshared')
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

    with pytest.raises(
        RuntimeError,
        match="Replacement migration source already claimed in unified corrections: ETHEREUM/0xshared",
    ):
        migrate_legacy_corrections(main_db_path=main_db_path, corrections_db_path=corrections_db_path)


def test_migrate_legacy_corrections_supports_old_note_not_null_schema(tmp_path: Path) -> None:
    main_db_path = tmp_path / "main.db"
    corrections_db_path = tmp_path / "corrections.db"
    _create_main_db(main_db_path)
    _create_old_unified_tables(corrections_db_path)
    _create_legacy_tables(corrections_db_path)

    main_engine = create_engine(f"sqlite:///{main_db_path}")
    with main_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO ledger_events (
                    id, timestamp, ingestion, origin_location, origin_external_id
                ) VALUES (
                    :id, '2024-02-01T10:00:00Z', 'raw', :origin_location, '0xactive'
                )
                """
            ),
            {
                "id": str(uuid4()),
                "origin_location": EventLocation.ARBITRUM.value,
            },
        )
    main_engine.dispose()

    corrections_engine = create_engine(f"sqlite:///{corrections_db_path}")
    with corrections_engine.begin() as connection:
        spam_id = str(uuid4())
        connection.execute(
            text(
                """
                INSERT INTO spam_corrections (
                    id, origin_location, origin_external_id, source, is_deleted
                ) VALUES (:id, :location, '0xactive', 'MANUAL', 0)
                """
            ),
            {"id": spam_id, "location": EventLocation.ARBITRUM.value},
        )
    migrate_legacy_corrections(main_db_path=main_db_path, corrections_db_path=corrections_db_path)
    with corrections_engine.begin() as connection:
        note = connection.execute(
            text(
                """
                SELECT c.note
                FROM ledger_corrections c
                JOIN ledger_correction_sources s ON s.correction_id = c.id
                WHERE s.origin_location = :location
                  AND s.origin_external_id = '0xactive'
                """
            ),
            {"location": EventLocation.ARBITRUM.value},
        ).scalar_one()
        assert note == ""
    corrections_engine.dispose()


def test_migrate_legacy_corrections_migrates_seed_opening_balances(tmp_path: Path) -> None:
    main_db_path = tmp_path / "main.db"
    corrections_db_path = tmp_path / "corrections.db"
    _create_main_db(main_db_path)
    _create_seed_tables(main_db_path)
    corrections_session = init_db_session(
        db_path=corrections_db_path,
        metadata=CorrectionsBase.metadata,
        reset=False,
    )
    corrections_session.close()

    main_engine = create_engine(f"sqlite:///{main_db_path}")
    with main_engine.begin() as connection:
        seed_id = str(uuid4())
        seed_leg_id = str(uuid4())
        connection.execute(
            text(
                """
                INSERT INTO seed_events (id, timestamp, price_per_token)
                VALUES (:id, '2000-01-01T00:00:00Z', '0')
                """
            ),
            {"id": seed_id},
        )
        connection.execute(
            text(
                """
                INSERT INTO seed_event_legs (
                    id, event_id, asset_id, quantity, account_chain_id, is_fee
                ) VALUES (:id, :event_id, 'BTC', '1.5', 'wallet', 0)
                """
            ),
            {"id": seed_leg_id, "event_id": seed_id},
        )
    main_engine.dispose()

    migrate_legacy_corrections(main_db_path=main_db_path, corrections_db_path=corrections_db_path)

    corrections_session = init_db_session(
        db_path=corrections_db_path,
        metadata=CorrectionsBase.metadata,
        reset=False,
    )
    repo = LedgerCorrectionRepository(corrections_session)
    corrections = repo.list()

    assert len(corrections) == 1
    correction = corrections[0]
    assert str(correction.id) == seed_id
    assert correction.timestamp == datetime(2000, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert len(correction.sources) == 0
    assert correction.price_per_token == Decimal("0")
    [leg] = correction.legs
    assert leg.asset_id == "BTC"
    assert leg.quantity == Decimal("1.5")
    assert leg.account_chain_id == "wallet"
    assert leg.is_fee is False
