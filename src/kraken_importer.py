from csv import DictReader
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class KrakenLedgerEntry(BaseModel):
    aclass: str
    amount: Decimal
    asset: str
    balance: Decimal
    fee: Decimal
    refid: str
    subtype: str
    time: datetime
    txid: str
    type: str
    wallet: str


class KrakenImporter:
    def __init__(self, source_path: str) -> None:
        self._source_path = source_path

    def ingest_data(self) -> list[KrakenLedgerEntry]:
        data = []
        try:
            with open(self._source_path, mode="r", encoding="utf-8") as file:
                reader = DictReader(file)  # Uses the first row as header
                for row in reader:
                    data.append(KrakenLedgerEntry.model_validate(row))
        except FileNotFoundError:
            print(f"Error: The file '{self._source_path}' was not found.")
        except Exception as e:
            print(f"An error occurred: {e}")

        return data
