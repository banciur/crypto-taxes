from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from accounts import KRAKEN_ACCOUNT_ID
from domain.acquisition_disposal import AcquisitionLot, DisposalLink
from domain.ledger import EventLegRef, EventLocation, EventOrigin, LegKey
from tests.constants import BASE_WALLET, BTC, ETH

TIMESTAMP = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)


def test_acquisition_lot_keeps_event_and_leg_identity_fields() -> None:
    quantity_acquired = Decimal("0.5")
    cost_per_unit = Decimal("20000")
    event_origin = EventOrigin(location=EventLocation.KRAKEN, external_id="acquisition")

    lot = AcquisitionLot(
        event_origin=event_origin,
        account_chain_id=KRAKEN_ACCOUNT_ID,
        asset_id=BTC,
        is_fee=False,
        timestamp=TIMESTAMP,
        quantity_acquired=quantity_acquired,
        cost_per_unit=cost_per_unit,
    )

    assert lot.event_origin == event_origin
    assert lot.account_chain_id == KRAKEN_ACCOUNT_ID
    assert lot.asset_id == BTC
    assert lot.timestamp == TIMESTAMP
    assert lot.quantity_acquired == quantity_acquired
    assert lot.cost_per_unit == cost_per_unit
    assert lot.leg_key == LegKey(account_chain_id=KRAKEN_ACCOUNT_ID, asset_id=BTC, is_fee=False)
    assert lot.source_leg_ref == EventLegRef(event_origin=event_origin, leg_key=lot.leg_key)


def test_disposal_link_keeps_event_and_leg_identity_fields() -> None:
    next_timestamp = datetime(2024, 1, 2, 12, tzinfo=timezone.utc)
    quantity_used = Decimal("0.2")
    proceeds_total = Decimal("500")
    event_origin = EventOrigin(location=EventLocation.BASE, external_id="disposal")

    lot = AcquisitionLot(
        event_origin=EventOrigin(location=EventLocation.KRAKEN, external_id="acquisition"),
        account_chain_id=KRAKEN_ACCOUNT_ID,
        asset_id=ETH,
        is_fee=False,
        timestamp=TIMESTAMP,
        quantity_acquired=Decimal("1"),
        cost_per_unit=Decimal("1500"),
    )
    link = DisposalLink(
        lot_id=lot.id,
        event_origin=event_origin,
        account_chain_id=BASE_WALLET,
        asset_id=ETH,
        is_fee=False,
        timestamp=next_timestamp,
        quantity_used=quantity_used,
        proceeds_total=proceeds_total,
    )

    assert link.lot_id == lot.id
    assert link.event_origin == event_origin
    assert link.account_chain_id == BASE_WALLET
    assert link.asset_id == ETH
    assert link.timestamp == next_timestamp
    assert link.quantity_used == quantity_used
    assert link.proceeds_total == proceeds_total
    assert link.leg_key == LegKey(account_chain_id=BASE_WALLET, asset_id=ETH, is_fee=False)
    assert link.source_leg_ref == EventLegRef(event_origin=event_origin, leg_key=link.leg_key)
