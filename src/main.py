from importers.kraken_importer import KrakenImporter


def main() -> None:
    kraken = KrakenImporter("./data/kraken-ledger.csv")
    kraken.perform_import()


if __name__ == "__main__":
    main()
