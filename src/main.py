from importers.kraken_importer import KrakenImporter


def main() -> None:
    kraken = KrakenImporter("./data/kraken-ledger.csv")
    kraken.load_events()


if __name__ == "__main__":
    main()
