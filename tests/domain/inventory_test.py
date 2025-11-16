from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from domain.inventory import InventoryEngine, InventoryResult
from domain.ledger import EventType, LedgerEvent, LedgerLeg
from tests.helpers.test_price_service import TestPriceService


@pytest.fixture(scope="function")
def inventory_engine() -> InventoryEngine:
    return InventoryEngine(price_provider=TestPriceService(seed=1))


WALLET_ID = "wallet"


def test_fifo_with_explicit_eur_legs(inventory_engine: InventoryEngine) -> None:
    t1 = datetime(2024, 9, 2, 12, 0, tzinfo=timezone.utc)
    t2 = datetime(2024, 9, 3, 12, 0, tzinfo=timezone.utc)
    t3 = datetime(2024, 9, 10, 12, 0, tzinfo=timezone.utc)

    buy1 = LedgerEvent(
        timestamp=t1,
        event_type=EventType.TRADE,
        legs=[
            LedgerLeg(asset_id="ETH", quantity=Decimal("1.0"), wallet_id=WALLET_ID),
            LedgerLeg(asset_id="EUR", quantity=Decimal("-3000"), wallet_id=WALLET_ID),
        ],
    )

    buy2 = LedgerEvent(
        timestamp=t2,
        event_type=EventType.TRADE,
        legs=[
            LedgerLeg(asset_id="ETH", quantity=Decimal("0.5"), wallet_id=WALLET_ID),
            LedgerLeg(asset_id="EUR", quantity=Decimal("-1500"), wallet_id=WALLET_ID),
        ],
    )

    sell1 = LedgerEvent(
        timestamp=t3,
        event_type=EventType.TRADE,
        legs=[
            LedgerLeg(asset_id="ETH", quantity=Decimal("-0.6"), wallet_id=WALLET_ID),
            LedgerLeg(asset_id="EUR", quantity=Decimal("2040"), wallet_id=WALLET_ID),
        ],
    )

    result: InventoryResult = inventory_engine.process([buy1, buy2, sell1])

    assert len(result.acquisition_lots) == 2
    assert all(lot.cost_eur_per_unit == Decimal("3000") for lot in result.acquisition_lots)

    assert len(result.disposal_links) == 1
    disposal_link = result.disposal_links[0]
    assert disposal_link.quantity_used == Decimal("0.6")
    assert disposal_link.proceeds_total_eur == Decimal("2040")

    assert [snap.quantity_remaining for snap in result.open_inventory] == [
        Decimal("0.4"),
        Decimal("0.5"),
    ]


def test_price_provider_when_no_eur_leg(inventory_engine: InventoryEngine) -> None:
    t1 = datetime(2024, 10, 1, 8, 0, tzinfo=timezone.utc)
    t2 = datetime(2024, 10, 5, 10, 0, tzinfo=timezone.utc)

    acquisition_rate = inventory_engine._price_provider.rate("BTC", "EUR", t1)
    disposal_rate = inventory_engine._price_provider.rate("BTC", "EUR", t2)

    # TODO this test uses not real scenario. Don't do it like this.
    airdrop = LedgerEvent(
        timestamp=t1,
        event_type=EventType.TRADE,
        legs=[
            LedgerLeg(asset_id="BTC", quantity=Decimal("2.0"), wallet_id=WALLET_ID),
        ],
    )

    payout = LedgerEvent(
        timestamp=t2,
        event_type=EventType.TRADE,
        legs=[
            LedgerLeg(asset_id="BTC", quantity=Decimal("-1.5"), wallet_id=WALLET_ID),
        ],
    )

    result = inventory_engine.process([airdrop, payout])

    assert len(result.acquisition_lots) == 1
    assert result.acquisition_lots[0].cost_eur_per_unit == acquisition_rate

    assert len(result.disposal_links) == 1
    disposal = result.disposal_links[0]
    assert disposal.quantity_used == Decimal("1.5")
    assert disposal.proceeds_total_eur == Decimal("1.5") * disposal_rate

    assert len(result.open_inventory) == 1
    remaining_snapshot = result.open_inventory[0]
    assert remaining_snapshot.quantity_remaining == Decimal("0.5")


def test_fee_leg_creates_disposal(inventory_engine: InventoryEngine) -> None:
    timestamp = datetime(2024, 10, 1, 12, 0, tzinfo=timezone.utc)
    link_rate = inventory_engine._price_provider.rate("LINK", "EUR", timestamp)

    link_reward = LedgerEvent(
        timestamp=timestamp,
        event_type=EventType.REWARD,
        legs=[
            LedgerLeg(asset_id="LINK", quantity=Decimal("5"), wallet_id=WALLET_ID),
        ],
    )

    ethtx = LedgerEvent(
        timestamp=timestamp,
        event_type=EventType.TRADE,
        legs=[
            LedgerLeg(asset_id="ETH", quantity=Decimal("1"), wallet_id=WALLET_ID),
            LedgerLeg(asset_id="EUR", quantity=Decimal("-1500"), wallet_id=WALLET_ID),
        ],
    )

    # TODO: this test uses not real scenario. Don't do it like this.
    swap_event = LedgerEvent(
        timestamp=timestamp,
        event_type=EventType.TRADE,
        legs=[
            LedgerLeg(asset_id="ETH", quantity=Decimal("-1"), wallet_id=WALLET_ID),
            LedgerLeg(asset_id="WBTC", quantity=Decimal("0.05"), wallet_id=WALLET_ID),
            LedgerLeg(asset_id="LINK", quantity=Decimal("-2"), wallet_id=WALLET_ID),
        ],
    )

    result = inventory_engine.process([link_reward, ethtx, swap_event])

    assert len(result.disposal_links) == 2  # ETH disposal + LINK fee disposal
    fee_disposal = next(link for link in result.disposal_links if link.quantity_used == Decimal("2"))
    assert fee_disposal.proceeds_total_eur == link_rate * Decimal("2")
