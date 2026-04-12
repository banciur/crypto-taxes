from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from domain.ledger import AccountChainId, AssetId, EventLocation, EventOrigin, LedgerEvent, LedgerLeg
from tests.constants import BASE_WALLET

BASE_TIMESTAMP = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
EXOTIC = AssetId("EXOTIC")


def make_event(
    *,
    external_id: str | None = None,
    legs: list[LedgerLeg],
    offset_days: int = 0,
    timestamp: datetime | None = None,
) -> LedgerEvent:
    event_timestamp = timestamp or (BASE_TIMESTAMP + timedelta(days=offset_days))
    return LedgerEvent(
        timestamp=event_timestamp,
        event_origin=EventOrigin(location=EventLocation.INTERNAL, external_id=external_id or str(uuid4())),
        ingestion="test",
        legs=legs,
    )


def make_leg(
    *,
    asset_id: AssetId,
    quantity: Decimal,
    account_chain_id: AccountChainId = BASE_WALLET,
    is_fee: bool = False,
) -> LedgerLeg:
    return LedgerLeg(
        asset_id=asset_id,
        quantity=quantity,
        account_chain_id=account_chain_id,
        is_fee=is_fee,
    )
