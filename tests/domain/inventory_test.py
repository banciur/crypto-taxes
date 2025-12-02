from __future__ import annotations

from decimal import Decimal

import pytest

from domain.inventory import InventoryEngine, InventoryError
from domain.ledger import EventType, LedgerLeg
from tests.helpers.test_price_service import TestPriceService
from tests.helpers.time_utils import DEFAULT_TIME_GEN, make_event


@pytest.fixture(scope="function")
def inventory_engine(price_service: TestPriceService) -> InventoryEngine:
    return InventoryEngine(price_provider=price_service)


WALLET_ID = "wallet"


def test_fifo(inventory_engine: InventoryEngine) -> None:
    t1_amount_bought = Decimal("1.0")
    t1_amount_spent = Decimal(2000)
    t1_leg = LedgerLeg(asset_id="ETH", quantity=t1_amount_bought, wallet_id=WALLET_ID)
    events = [
        make_event(
            event_type=EventType.TRADE,
            legs=[
                t1_leg,
                LedgerLeg(asset_id="EUR", quantity=-t1_amount_spent, wallet_id=WALLET_ID),
            ],
        )
    ]

    t2_amount_bought = Decimal("0.5")
    t2_amount_spent = Decimal(2200)
    t2_leg = LedgerLeg(asset_id="ETH", quantity=t2_amount_bought, wallet_id=WALLET_ID)
    events.append(
        make_event(
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
        make_event(
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
        make_event(
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
    assert lot_1.acquired_leg_id == t1_leg.id
    assert lot_1.cost_per_unit == t1_amount_spent / t1_amount_bought

    lot_2 = result.acquisition_lots[1]
    assert lot_2.acquired_leg_id == t2_leg.id
    assert lot_2.cost_per_unit == t2_amount_spent / t2_amount_bought

    dl_1 = result.disposal_links[0]
    assert dl_1.lot_id == lot_1.id
    assert dl_1.disposal_leg_id == t3_leg.id
    assert dl_1.quantity_used == t3_amount_spent
    assert dl_1.proceeds_total == t3_amount_bought

    dl_2 = result.disposal_links[1]
    assert dl_2.lot_id == lot_1.id
    assert dl_2.disposal_leg_id == t4_leg.id
    d2_expected_quantity = t1_amount_bought - t3_amount_spent
    assert dl_2.quantity_used == d2_expected_quantity
    assert dl_2.proceeds_total == d2_expected_quantity * (t4_amount_bought / t4_amount_spent)

    dl_3 = result.disposal_links[2]
    assert dl_3.lot_id == lot_2.id
    assert dl_3.disposal_leg_id == t4_leg.id
    d3_expected_quantity = t4_amount_spent - d2_expected_quantity
    assert dl_3.quantity_used == d3_expected_quantity
    assert dl_3.proceeds_total == d3_expected_quantity * (t4_amount_bought / t4_amount_spent)

    assert len(result.open_inventory) == 1
    open_lot = result.open_inventory[0]

    assert open_lot.lot_id == lot_2.id
    assert open_lot.quantity_remaining == t2_amount_bought - d3_expected_quantity


def test_obtaining_price_from_provider(inventory_engine: InventoryEngine) -> None:
    t1_amount_bought = Decimal("1.0")
    t1_amount_spent = Decimal(2000)
    t1_leg = LedgerLeg(asset_id="ETH", quantity=t1_amount_bought, wallet_id=WALLET_ID)
    events = [
        make_event(
            event_type=EventType.TRADE,
            legs=[
                t1_leg,
                LedgerLeg(asset_id="EUR", quantity=-t1_amount_spent, wallet_id=WALLET_ID),
            ],
        )
    ]

    t2_time = DEFAULT_TIME_GEN.next()
    t2_amount_dropped = Decimal("0.6")
    t2_amount_fee = Decimal("0.0001")
    t2_drop_leg = LedgerLeg(asset_id="SPK", quantity=t2_amount_dropped, wallet_id=WALLET_ID)
    t2_fee_leg = LedgerLeg(asset_id="ETH", quantity=-t2_amount_fee, wallet_id=WALLET_ID, is_fee=True)
    events.append(make_event(event_type=EventType.REWARD, legs=[t2_drop_leg, t2_fee_leg], timestamp=t2_time))
    result = inventory_engine.process(events)

    assert len(result.acquisition_lots) == 2
    assert len(result.disposal_links) == 1

    lot_2 = result.acquisition_lots[1]
    assert lot_2.acquired_leg_id == t2_drop_leg.id
    drop_rate = inventory_engine._price_provider.rate("SPK", "EUR", t2_time)
    assert lot_2.cost_per_unit == drop_rate

    disposal = result.disposal_links[0]
    assert disposal.disposal_leg_id == t2_fee_leg.id
    assert disposal.quantity_used == abs(t2_fee_leg.quantity)
    fee_rate = inventory_engine._price_provider.rate("ETH", "EUR", t2_time)
    assert disposal.proceeds_total == fee_rate * disposal.quantity_used

    assert len(result.open_inventory) == 2
    open_lot_eth = result.open_inventory[0]
    open_lot_spk = result.open_inventory[1]

    assert open_lot_eth.lot_id == result.acquisition_lots[0].id
    assert open_lot_eth.quantity_remaining == t1_amount_bought - t2_amount_fee

    assert open_lot_spk.lot_id == lot_2.id
    assert open_lot_spk.quantity_remaining == t2_amount_dropped


def test_transfers_dont_create_acquisition(inventory_engine: InventoryEngine) -> None:
    kraken_wallet = "kraken"
    hardware_wallet = "ledger"

    buy_amount = Decimal("1.5")
    transfer_amount = Decimal("0.5")
    buy_spent_eur = Decimal("3000")
    buy_leg = LedgerLeg(asset_id="ETH", quantity=buy_amount, wallet_id=kraken_wallet)
    events = [
        make_event(
            event_type=EventType.TRADE,
            legs=[
                buy_leg,
                LedgerLeg(asset_id="EUR", quantity=-buy_spent_eur, wallet_id=kraken_wallet),
            ],
        ),
        make_event(
            event_type=EventType.TRANSFER,
            legs=[
                LedgerLeg(asset_id="ETH", quantity=transfer_amount, wallet_id=hardware_wallet),
                LedgerLeg(asset_id="ETH", quantity=-transfer_amount, wallet_id=kraken_wallet),
            ],
        ),
    ]

    result = inventory_engine.process(events)

    assert len(result.acquisition_lots) == 1
    acquisition_lot = result.acquisition_lots[0]
    assert acquisition_lot.acquired_leg_id == buy_leg.id
    assert acquisition_lot.cost_per_unit == buy_spent_eur / buy_amount

    assert result.disposal_links == []

    assert len(result.open_inventory) == 1
    open_lot = result.open_inventory[0]
    assert open_lot.acquired_timestamp == events[0].timestamp
    assert open_lot.lot_id == acquisition_lot.id
    assert open_lot.quantity_remaining == buy_amount


def test_disposal_without_inventory_raises(inventory_engine: InventoryEngine) -> None:
    events = [
        make_event(
            event_type=EventType.TRADE,
            legs=[
                LedgerLeg(asset_id="ETH", quantity=Decimal("-1.0"), wallet_id=WALLET_ID),
                LedgerLeg(asset_id="EUR", quantity=Decimal("2500"), wallet_id=WALLET_ID),
            ],
        )
    ]

    with pytest.raises(InventoryError):
        inventory_engine.process(events)


def test_transfer_without_inventory_is_skipped(inventory_engine: InventoryEngine) -> None:
    events = [
        make_event(
            event_type=EventType.TRANSFER,
            legs=[
                LedgerLeg(asset_id="ETH", quantity=Decimal("1.0"), wallet_id="ledger"),
                LedgerLeg(asset_id="ETH", quantity=Decimal("-1.0"), wallet_id="kraken"),
            ],
        )
    ]

    result = inventory_engine.process(events)
    assert result.acquisition_lots == []
    assert result.disposal_links == []
    assert result.open_inventory == []
