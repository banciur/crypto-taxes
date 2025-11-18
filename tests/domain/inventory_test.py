from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from domain.inventory import InventoryEngine
from domain.ledger import EventType, LedgerEvent, LedgerLeg
from tests.helpers.test_price_service import TestPriceService


@pytest.fixture(scope="function")
def inventory_engine() -> InventoryEngine:
    return InventoryEngine(price_provider=TestPriceService(seed=1))


WALLET_ID = "wallet"


def test_fifo(inventory_engine: InventoryEngine) -> None:
    events: list[LedgerEvent] = []

    t1_amount_bought = Decimal("1.0")
    t1_amount_spent = Decimal(2000)
    t1_leg = LedgerLeg(asset_id="ETH", quantity=t1_amount_bought, wallet_id=WALLET_ID)
    events.append(
        LedgerEvent(
            timestamp=datetime(2024, 9, 2, 12, tzinfo=timezone.utc),
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
            timestamp=datetime(2024, 9, 3, 12, tzinfo=timezone.utc),
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
            timestamp=datetime(2024, 9, 10, 12, tzinfo=timezone.utc),
            event_type=EventType.TRADE,
            legs=[
                t3_leg,
                LedgerLeg(asset_id="EUR", quantity=t3_amount_bought, wallet_id=WALLET_ID),
            ],
        )
    )

    # This should create two disposals as the amount is bigger than amount left in the first lot.
    t4_amount_spent = Decimal("0.7")
    t4_amount_bought = Decimal(1900)
    t4_leg = LedgerLeg(asset_id="ETH", quantity=-t4_amount_spent, wallet_id=WALLET_ID)
    events.append(
        LedgerEvent(
            timestamp=datetime(2024, 9, 10, 12, tzinfo=timezone.utc),
            event_type=EventType.TRADE,
            legs=[
                t4_leg,
                LedgerLeg(asset_id="EUR", quantity=t4_amount_bought, wallet_id=WALLET_ID),
            ],
        )
    )

    result = inventory_engine.process(events)

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

    assert len(result.open_inventory) == 1
    open_lot = result.open_inventory[0]

    assert open_lot.lot_id == lot_2.id
    assert open_lot.quantity_remaining == t2_amount_bought - d3_expected_quantity


def test_obtaining_price_from_provider(inventory_engine: InventoryEngine) -> None:
    events: list[LedgerEvent] = []

    t1_amount_bought = Decimal("1.0")
    t1_amount_spent = Decimal(2000)
    t1_leg = LedgerLeg(asset_id="ETH", quantity=t1_amount_bought, wallet_id=WALLET_ID)
    events.append(
        LedgerEvent(
            timestamp=datetime(2024, 9, 2, 12, tzinfo=timezone.utc),
            event_type=EventType.TRADE,
            legs=[
                t1_leg,
                LedgerLeg(asset_id="EUR", quantity=-t1_amount_spent, wallet_id=WALLET_ID),
            ],
        )
    )

    t2_time = datetime(2024, 10, 5, 10, tzinfo=timezone.utc)
    t2_amount_dropped = Decimal("0.6")
    t2_amount_fee = Decimal("0.0001")
    t2_drop_leg = LedgerLeg(asset_id="SPK", quantity=t2_amount_dropped, wallet_id=WALLET_ID)
    t2_fee_leg = LedgerLeg(asset_id="ETH", quantity=-t2_amount_fee, wallet_id=WALLET_ID)
    events.append(
        LedgerEvent(
            timestamp=t2_time,
            event_type=EventType.DROP,
            legs=[
                t2_drop_leg,
                t2_fee_leg,
            ],
        )
    )
    result = inventory_engine.process(events)

    assert len(result.acquisition_lots) == 2
    assert len(result.disposal_links) == 1

    lot_2 = result.acquisition_lots[1]
    assert lot_2.acquired_event_id == events[1].id
    assert lot_2.acquired_leg_id == t2_drop_leg.id
    drop_rate = inventory_engine._price_provider.rate("SPK", "EUR", t2_time)
    assert lot_2.cost_eur_per_unit == drop_rate

    disposal = result.disposal_links[0]
    assert disposal.disposal_leg_id == t2_fee_leg.id
    assert disposal.quantity_used == abs(t2_fee_leg.quantity)
    fee_rate = inventory_engine._price_provider.rate("ETH", "EUR", t2_time)
    assert disposal.proceeds_total_eur == fee_rate * disposal.quantity_used

    assert len(result.open_inventory) == 2
    open_lot_eth = result.open_inventory[0]
    open_lot_spk = result.open_inventory[1]

    assert open_lot_eth.lot_id == result.acquisition_lots[0].id
    assert open_lot_eth.quantity_remaining == t1_amount_bought - t2_amount_fee

    assert open_lot_spk.lot_id == lot_2.id
    assert open_lot_spk.quantity_remaining == t2_amount_dropped
