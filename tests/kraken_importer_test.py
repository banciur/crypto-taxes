from collections.abc import Generator
from csv import DictWriter
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, Engine, select
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base, Ledger
from kraken_importer import KrakenImporter, KrakenLedgerEntry
from utils import generate_random_string


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    engine: Engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_maker = sessionmaker(engine)
    with session_maker() as session:
        yield session


def get_ledger_arr() -> dict:
    return {
        "aclass": "currency",
        "txid": generate_random_string(10),
        "time": datetime.now(),
        "wallet": "spot / main",
    }


def test_kraken_importer(db_session: Session, tmp_path: Path) -> None:
    # This tests just one case
    file = tmp_path / "mock.csv"

    refdid = "come_refId"

    records = [
        KrakenLedgerEntry.model_validate(
            {
                **get_ledger_arr(),
                "amount": Decimal(5),
                "asset": "ETH",
                "balance": Decimal(5),
                "fee": Decimal(0),
                "refid": generate_random_string(10),
                "type": "earn",
                "subtype": "reward",
                "wallet": "earn / bonded",
            }
        ),
        KrakenLedgerEntry.model_validate(
            {
                **get_ledger_arr(),
                "amount": Decimal(10),
                "asset": "USD",
                "balance": Decimal(0),
                "fee": Decimal(0),
                "refid": refdid,
                "subtype": "allocation",
                "type": "earn",
                "wallet": "spot / main",
            }
        ),
        KrakenLedgerEntry.model_validate(
            {
                **get_ledger_arr(),
                "amount": Decimal(-10),
                "asset": "USD",
                "balance": Decimal(10),
                "fee": Decimal(0),
                "refid": refdid,
                "subtype": "allocation",
                "type": "earn",
                "wallet": "earn / flexible",
            }
        ),
    ]

    with open(file, "w", newline="") as csvfile:
        fieldnames = list(KrakenLedgerEntry.model_fields.keys())
        writer = DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        data = records[0].model_dump()

        writer.writerow(data)

    importer = KrakenImporter(str(file), db_session)
    importer.perform_import()

    stmt = select(Ledger)
    res = list(db_session.execute(stmt).scalars())
    assert len(res) == 1
