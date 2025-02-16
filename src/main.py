from db.db import init_db
from kraken_importer import KrakenImporter


def main() -> None:
    session = init_db()
    kraken = KrakenImporter("./data/kraken-ledger.csv", session)
    kraken.perform_import()


if __name__ == "__main__":
    main()
