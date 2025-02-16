from db.db import init_db
from kraken_importer import KrakenImporter
from reports import get_token_amounts


def main() -> None:
    session = init_db()
    kraken = KrakenImporter("./data/kraken-ledger.csv", session)
    kraken.perform_import()
    get_token_amounts(session)


if __name__ == "__main__":
    main()
