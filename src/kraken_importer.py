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


# TODO: not handled correctly take a look into files
# transfer	stakingfromspot FTdpE2Z-ZC7GPkNJbcCEJ7DPO01Vsa
# transfer	spottostaking FTa8sFl-oaAXHEhrpwIwGFOOzgxgfh


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
        refid_map: dict[str, list[KrakenLedgerEntry]] = defaultdict(list)
        types = set()
        subtype = set()
        wallet = set()
        for e in entries:
            refid_map[e.refid].append(e)
            types.add(e.type)
            subtype.add(e.subtype)
            wallet.add(e.wallet)

        for refid, lines in refid_map.items():
            if refid == "ELFI6E5-PNXZG-NSGNER":
                # Those are 4 operations on BTC where it was automatically moved between earn types but token stayed the same so nothing to do
                # "LSGSVB-OHSHV-NQ5NUN", "ELFI6E5-PNXZG-NSGNER", "2024-04-17 20:36:43", "earn", "allocation", "currency", "BTC", "spot / main", -0.0000099500, 0, 0.0000000000
                # "L3SUVI-QSFMZ-624QPQ", "ELFI6E5-PNXZG-NSGNER", "2024-04-17 20:36:43", "earn", "allocation", "currency", "BTC", "earn / flexible", 0.0000099500, 0, 0.0000099500
                # "L5ZXEE-YEAID-PCBXU3", "ELFI6E5-PNXZG-NSGNER", "2024-09-10 13:48:39", "earn", "deallocation", "currency", "BTC", "earn / flexible", -0.0000099539, 0, 0.0000000000
                # "LC4QJU-V2LOI-CCHQRM", "ELFI6E5-PNXZG-NSGNER", "2024-09-10 13:48:39", "earn", "allocation", "currency", "BTC", "earn / locked", 0.0000099539, 0, 0.0000099539
                continue

            date = lines[0].time

            combined_txids = [line.txid for line in lines]

            # Compute fee
            fee_lines = [line for line in lines if line.fee != 0]
            if len(fee_lines) == 0:
                fee = 0
                fee_currency = None
            elif len(fee_lines) == 1:
                fee = decimal_to_int(fee_lines[0].fee)
                fee_currency = fee_lines[0].asset
            else:
                raise Exception(f"Multiple fee lines for refid {refid}, but expected exactly one.")

            ledger_entry = Ledger(
                date=date,
                external_id=refid,
                operation_place=operation_place,
                fee=fee,
                fee_currency=fee_currency,
                transactions=combined_txids,
            )
            if len(lines) == 2:
                out_line = next((ln for ln in lines if ln.amount < 0), None)
                in_line = next((ln for ln in lines if ln.amount > 0), None)

                line_types = set([ln.type for ln in lines])
                line_subtypes = set([ln.subtype for ln in lines])

                operation_type = "trade"
                note = None

                if lines[0].type == lines[1].type == "trade":
                    # Nothing special to do this is typical case
                    pass
                elif lines[0].type == lines[1].type == "earn":
                    if lines[0].subtype == lines[1].subtype in ["allocation", "deallocation"] or line_subtypes == {
                        "allocation",
                        "deallocation",
                    }:
                        # earn (de) allocation when both assets are same type, same amount and no fee it means this is not interesting for me
                        assert lines[0].asset == lines[1].asset
                        assert fee == 0
                        assert lines[0].amount == -1 * lines[1].amount
                        continue
                    elif lines[0].subtype == lines[1].subtype == "migration":
                        assert lines[0].amount == -1 * lines[1].amount
                        assert fee == 0
                        # This one is case when one currency was migrated to another. For me this changes token type which has tax consequences.
                        # I'll treat this as a normal trade just add note

                        note = "It was migration probably automatic"
                    else:
                        print(f'"{refid}" with double lines of type earn which are not handled by import.')
                elif line_types == {"spend", "receive"}:
                    # Seems that spend and receive is another type of trade. Happens during "dustsweeping" but also other cases which are unknown to me.
                    pass
                else:
                    # Refid with multiple lines wich are not trade
                    print(
                        f'"{refid}" with double lines of type {", ".join(line_types)} which are not handled by import."'
                    )
                    operation_type = lines[0].type

                if out_line and in_line:
                    ledger_entry.out_currency = out_line.asset
                    ledger_entry.out_amount = abs(decimal_to_int(out_line.amount))
                    ledger_entry.in_currency = in_line.asset
                    ledger_entry.in_amount = abs(decimal_to_int(in_line.amount))
                    ledger_entry.operation_type = operation_type
                    ledger_entry.note = note
                else:
                    raise Exception(
                        f"Ledger entry '{refid}' could not be imported it is not pair positive / negative amount"
                    )
            elif len(lines) == 1:
                # Single line: deposit or withdrawal
                line = lines[0]
                amt = decimal_to_int(line.amount)
                ledger_entry.out_currency = line.asset

                if line.amount < 0:
                    # Withdrawal (out)
                    ledger_entry.out_amount = abs(amt)
                    ledger_entry.operation_type = "withdrawal"
                else:
                    # Deposit (in)
                    ledger_entry.in_amount = amt
                    ledger_entry.operation_type = "deposit"
            else:
                raise Exception(f"More then two Kraken Ledger entries with {refid}")

            self._session.add(ledger_entry)

        # print(types)
        # print(subtype)
        # print(wallet)

        self._session.commit()

    def perform_import(self) -> None:
        data = self._read_data()
        self._import_kraken_ledger_entries(data)
