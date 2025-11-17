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
    events: list[LedgerEvent] = []

    t1_amount_bought = Decimal("1.0")
    t1_amount_spent = Decimal(2000)
    t1_leg = LedgerLeg(asset_id="ETH", quantity=t1_amount_bought, wallet_id=WALLET_ID)
    events.append(
        LedgerEvent(
            timestamp=datetime(2024, 9, 2, 12, 0, tzinfo=timezone.utc),
            event_type=EventType.TRADE,
            legs=[
                t1_leg,
                LedgerLeg(asset_id="EUR", quantity=-t1_amount_spent, wallet_id=WALLET_ID),
            ],
        )
    )

    t2_amount_bought = Decimal("0.5")
    t2_amount_spent = Decimal(2200)
    t2_leg = LedgerLeg(asset_id="ETH", quantity=t2_amount_bought, wallet_id=WALLET_ID)
    events.append(
        LedgerEvent(
            timestamp=datetime(2024, 9, 3, 12, 0, tzinfo=timezone.utc),
            event_type=EventType.TRADE,
            legs=[
                t2_leg,
                LedgerLeg(asset_id="EUR", quantity=-t2_amount_spent, wallet_id=WALLET_ID),
            ],
        )
    )

    t3_amount_spent = Decimal("0.6")
    t3_amount_bought = Decimal(2040)
    t3_leg = LedgerLeg(asset_id="ETH", quantity=-t3_amount_spent, wallet_id=WALLET_ID)
    events.append(
        LedgerEvent(
            timestamp=datetime(2024, 9, 10, 12, 0, tzinfo=timezone.utc),
            event_type=EventType.TRADE,
            legs=[
                t3_leg,
                LedgerLeg(asset_id="EUR", quantity=t3_amount_bought, wallet_id=WALLET_ID),
            ],
        )
    )

    # This should create two disposals
    t4_amount_spent = Decimal("0.7")
    t4_amount_bought = Decimal(1900)
    t4_leg = LedgerLeg(asset_id="ETH", quantity=-t4_amount_spent, wallet_id=WALLET_ID)
    events.append(
        LedgerEvent(
            timestamp=datetime(2024, 9, 10, 12, 1, tzinfo=timezone.utc),
            event_type=EventType.TRADE,
            legs=[
                t4_leg,
                LedgerLeg(asset_id="EUR", quantity=t4_amount_bought, wallet_id=WALLET_ID),
            ],
        )
    )

    result: InventoryResult = inventory_engine.process(events)

    assert len(result.acquisition_lots) == 2
    assert len(result.disposal_links) == 3

    lot_1 = result.acquisition_lots[0]
    assert lot_1.acquired_event_id == events[0].id
    assert lot_1.acquired_leg_id == t1_leg.id
    assert lot_1.cost_eur_per_unit == t1_amount_spent / t1_amount_bought

    lot_2 = result.acquisition_lots[1]
    assert lot_2.acquired_event_id == events[1].id
    assert lot_2.acquired_leg_id == t2_leg.id
    assert lot_2.cost_eur_per_unit == t2_amount_spent / t2_amount_bought

    dl_1 = result.disposal_links[0]
    assert dl_1.lot_id == lot_1.id
    assert dl_1.disposal_leg_id == t3_leg.id
    assert dl_1.quantity_used == t3_amount_spent
    assert dl_1.proceeds_total_eur == t3_amount_bought

    dl_2 = result.disposal_links[1]
    assert dl_2.lot_id == lot_1.id
    assert dl_2.disposal_leg_id == t4_leg.id
    d2_expected_quantity = t1_amount_bought - t3_amount_spent
    assert dl_2.quantity_used == d2_expected_quantity
    assert dl_2.proceeds_total_eur == d2_expected_quantity * (t4_amount_bought / t4_amount_spent)

    dl_3 = result.disposal_links[2]
    assert dl_3.lot_id == lot_2.id
    assert dl_3.disposal_leg_id == t4_leg.id
    d3_expected_quantity = t4_amount_spent - d2_expected_quantity
    assert dl_3.quantity_used == d3_expected_quantity
    assert dl_3.proceeds_total_eur == d3_expected_quantity * (t4_amount_bought / t4_amount_spent)


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
