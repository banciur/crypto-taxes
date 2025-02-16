from csv import DictReader
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel
from collections import defaultdict
from sqlalchemy.orm import Session

from db.models import Ledger
from utils import decimal_to_int


class KrakenLedgerEntry(BaseModel):
    aclass: str  # For all entries that I have it is "currency"
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
    def __init__(self, source_path: str, session: Session) -> None:
        self._source_path = source_path
        self._session = session

    def _read_data(self) -> list[KrakenLedgerEntry]:
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

    def _import_kraken_ledger_entries(
        self,
        entries: list[KrakenLedgerEntry],
    ) -> None:
        operation_place: str = "Kraken"
        # Group by refid
        refid_map: dict[str, list[KrakenLedgerEntry]] = defaultdict(list)
        type = set()
        subtype = set()
        wallet = set()
        for e in entries:
            refid_map[e.refid].append(e)
            type.add(e.type)
            subtype.add(e.subtype)
            wallet.add(e.wallet)

        for refid, lines in refid_map.items():
            if refid == "ELFI6E5-PNXZG-NSGNER":
                # Those are 4 strange operations on BTC where it was automatically moved between earn types
                # "LSGSVB-OHSHV-NQ5NUN", "ELFI6E5-PNXZG-NSGNER", "2024-04-17 20:36:43", "earn", "allocation", "currency", "BTC", "spot / main", -0.0000099500, 0, 0.0000000000
                # "L3SUVI-QSFMZ-624QPQ", "ELFI6E5-PNXZG-NSGNER", "2024-04-17 20:36:43", "earn", "allocation", "currency", "BTC", "earn / flexible", 0.0000099500, 0, 0.0000099500
                # "L5ZXEE-YEAID-PCBXU3", "ELFI6E5-PNXZG-NSGNER", "2024-09-10 13:48:39", "earn", "deallocation", "currency", "BTC", "earn / flexible", -0.0000099539, 0, 0.0000000000
                # "LC4QJU-V2LOI-CCHQRM", "ELFI6E5-PNXZG-NSGNER", "2024-09-10 13:48:39", "earn", "allocation", "currency", "BTC", "earn / locked", 0.0000099539, 0, 0.0000099539
                continue

            date = lines[0].time

            combined_txids = [line.txid for line in lines]
            # TODO: Kraken fees are computed incorrectly
            total_fee = sum(decimal_to_int(line.fee) for line in lines if line.fee is not None)

            ledger_entry = Ledger(
                date=date,
                external_id=refid,
                operation_place=operation_place,
                fee=total_fee,
                transactions=combined_txids,
            )
            if len(lines) == 2:
                out_line = next((ln for ln in lines if ln.amount < 0), None)
                in_line = next((ln for ln in lines if ln.amount > 0), None)

                if out_line and in_line:
                    ledger_entry.out_currency = out_line.asset
                    ledger_entry.out_amount = abs(decimal_to_int(out_line.amount))
                    ledger_entry.in_currency = in_line.asset
                    ledger_entry.in_amount = abs(decimal_to_int(in_line.amount))
                    ledger_entry.operation_type = "trade"
                else:
                    raise Exception(f"Ledger entry '{refid}' could not be imported not one over and another under")
            elif len(lines) == 1:
                # Single line: deposit or withdrawal
                line = lines[0]
                amt = decimal_to_int(line.amount)
                if line.amount < 0:
                    # Withdrawal (out)
                    ledger_entry.out_currency = line.asset
                    ledger_entry.out_amount = abs(amt)
                    ledger_entry.operation_type = "withdrawal"
                else:
                    # Deposit (in)
                    ledger_entry.in_currency = line.asset
                    ledger_entry.in_amount = amt
                    ledger_entry.operation_type = "deposit"
            else:
                raise Exception(f"More then two Kraken Ledger entries with {refid}")

            self._session.add(ledger_entry)

        print(type)
        print(subtype)
        print(wallet)

        self._session.commit()

    def perform_import(self) -> None:
        data = self._read_data()
        self._import_kraken_ledger_entries(data)
