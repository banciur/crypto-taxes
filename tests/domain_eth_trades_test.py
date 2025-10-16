from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from domain.ledger import (
    AcquisitionLot,
    DisposalLink,
    EventType,
    LedgerEvent,
    LedgerLeg,
)
from domain.pricing import PriceSnapshot


def test_eth_trading_flow_simple() -> None:
    """Simulate starting with EUR, then buying and selling ETH.

    This test focuses on constructing domain models that represent a simple
    sequence of actions without running a full valuation or inventory engine.
    """

    # Price snapshots (EUR quote) at each time point for ETH.
    t1 = datetime(2024, 9, 2, 12, 0, tzinfo=timezone.utc)
    t2 = datetime(2024, 9, 3, 12, 0, tzinfo=timezone.utc)
    t3 = datetime(2024, 9, 10, 12, 0, tzinfo=timezone.utc)

    px_t1 = PriceSnapshot(timestamp=t1, base_id="ETH", quote_id="EUR", rate=Decimal("3000"), source="mock")
    px_t2 = PriceSnapshot(timestamp=t2, base_id="ETH", quote_id="EUR", rate=Decimal("3000"), source="mock")
    px_t3 = PriceSnapshot(timestamp=t3, base_id="ETH", quote_id="EUR", rate=Decimal("3400"), source="mock")

    wallet_id = "hot_mm"

    # 2) Buy 1.0 ETH for 3000 EUR at t1 (exclude fees for simplicity)
    buy1 = LedgerEvent(
        timestamp=t1,
        event_type=EventType.TRADE,
        legs=[
            LedgerLeg(asset_id="ETH", quantity=Decimal("1.0"), wallet_id=wallet_id),
            LedgerLeg(asset_id="EUR", quantity=Decimal("-3000"), wallet_id=wallet_id),
        ],
    )

    lot1 = AcquisitionLot(
        acquired_event_id=buy1.id,
        acquired_leg_id=buy1.legs[0].id,
        cost_eur_per_unit=px_t1.rate,  # 3000 EUR/ETH
    )

    # 3) Buy 0.5 ETH for 1500 EUR at t2
    buy2 = LedgerEvent(
        timestamp=t2,
        event_type=EventType.TRADE,
        legs=[
            LedgerLeg(asset_id="ETH", quantity=Decimal("0.5"), wallet_id=wallet_id),
            LedgerLeg(asset_id="EUR", quantity=Decimal("-1500"), wallet_id=wallet_id),
        ],
    )

    lot2 = AcquisitionLot(
        acquired_event_id=buy2.id,
        acquired_leg_id=buy2.legs[0].id,
        cost_eur_per_unit=px_t2.rate,  # 3000 EUR/ETH
    )

    # 4) Sell 0.6 ETH at t3 when ETH is 3400 EUR
    sell1 = LedgerEvent(
        timestamp=t3,
        event_type=EventType.TRADE,
        legs=[
            LedgerLeg(asset_id="ETH", quantity=Decimal("-0.6"), wallet_id=wallet_id),
            LedgerLeg(asset_id="EUR", quantity=Decimal("2040"), wallet_id=wallet_id),  # 0.6 * 3400
        ],
    )

    # FIFO consumption: consume 0.6 ETH from lot1
    proceeds = Decimal("0.6") * px_t3.rate  # 2040 EUR
    disposal = DisposalLink(
        disposal_leg_id=sell1.legs[0].id,
        lot_id=lot1.id,
        quantity_used=Decimal("0.6"),
        proceeds_total_eur=proceeds,
    )

    # Simulated remaining for lot1 after disposal (inventory engine not implemented yet)
    # Derive the acquired quantity from the acquisition leg (normalized model)
    acquired_qty_lot1 = buy1.legs[0].quantity
    remaining_lot1 = acquired_qty_lot1 - disposal.quantity_used

    # Assertions reflecting our simple scenario
    assert buy1.event_type == EventType.TRADE and buy2.event_type == EventType.TRADE
    assert sell1.event_type == EventType.TRADE

    assert remaining_lot1 == Decimal("0.4")  # 1.0 - 0.6
    assert buy2.legs[0].quantity == Decimal("0.5") and lot2.cost_eur_per_unit == Decimal("3000")
    assert disposal.proceeds_total_eur == Decimal("2040")
