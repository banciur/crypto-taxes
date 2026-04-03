from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from domain.ledger import (
    DuplicateLegIdentityError,
    EventLocation,
    EventOrigin,
    LedgerEvent,
    LedgerLeg,
)
from tests.constants import ETH, LEDGER_WALLET

TIMESTAMP = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)


def _ledger_leg(*, quantity: Decimal, is_fee: bool = False) -> LedgerLeg:
    return LedgerLeg(
        asset_id=ETH,
        quantity=quantity,
        account_chain_id=LEDGER_WALLET,
        is_fee=is_fee,
    )


def test_ledger_event_rejects_duplicate_leg_identity() -> None:
    with pytest.raises(ValidationError, match="duplicate leg identities") as exc_info:
        LedgerEvent(
            timestamp=TIMESTAMP,
            event_origin=EventOrigin(location=EventLocation.INTERNAL, external_id="duplicate-legs"),
            ingestion="test",
            legs=[
                _ledger_leg(quantity=Decimal("1")),
                _ledger_leg(quantity=Decimal("2")),
            ],
        )

    error = exc_info.value.errors()[0]["ctx"]["error"]
    assert isinstance(error, DuplicateLegIdentityError)
    assert error.duplicates == ((LEDGER_WALLET, ETH, False),)


def test_ledger_event_allows_same_account_and_asset_when_fee_flag_differs() -> None:
    event = LedgerEvent(
        timestamp=TIMESTAMP,
        event_origin=EventOrigin(location=EventLocation.INTERNAL, external_id="fee-distinguishes-leg"),
        ingestion="test",
        legs=[
            _ledger_leg(quantity=Decimal("1")),
            _ledger_leg(quantity=Decimal("-0.01"), is_fee=True),
        ],
    )

    assert len(event.legs) == 2
