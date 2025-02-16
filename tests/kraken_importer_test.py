from typing import cast

import pytest
from sqlalchemy.orm import Session

from kraken_importer import KrakenImporter


@pytest.fixture(scope="function")
def kraken_importer() -> KrakenImporter:
    return KrakenImporter(".data/kraken-ledger.csv", cast(Session, None))


def test_hello_world(kraken_importer: KrakenImporter) -> None:
    assert True
