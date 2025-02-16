from collections import defaultdict

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from db.models import Ledger
from utils import int_to_decimal


def get_token_amounts(session: Session):
    aggregator: dict[str, int] = defaultdict(int)

    stmt = select(Ledger)
    for entry in session.scalars(stmt):
        if entry.in_currency and entry.in_amount:
            aggregator[entry.in_currency] += entry.in_amount
        if entry.out_currency and entry.out_amount:
            aggregator[entry.out_currency] -= entry.out_amount
        if entry.fee_currency and entry.fee:
            aggregator[entry.fee_currency] -= entry.fee

    for currency, amount in aggregator.items():
        print(currency, int_to_decimal(amount))