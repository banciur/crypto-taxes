from sqlalchemy.orm import Session

from db.db import init_db
from kraken_importer import KrakenImporter


def main() -> None:
    _session: Session = init_db()
    kraken = KrakenImporter("./data/kraken-ledger.csv")
    kraken.ingest_data()


if __name__ == "__main__":
    main()
