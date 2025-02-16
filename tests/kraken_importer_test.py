import pytest

from kraken_importer import KrakenImporter


@pytest.fixture(scope="function")
def kraken_importer() -> KrakenImporter:
    return KrakenImporter(".data/kraken-ledger.csv")


def test_hello_world(kraken_importer: KrakenImporter) -> None:
    assert True
