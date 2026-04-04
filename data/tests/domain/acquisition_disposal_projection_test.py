from __future__ import annotations

from decimal import Decimal

import pytest

from accounts import KRAKEN_ACCOUNT_ID
from domain.acquisition_disposal_projection import (
    AcquisitionDisposalProjectionError,
    AcquisitionDisposalProjector,
)
from domain.ledger import AccountChainId, AssetId, LedgerLeg
from tests.constants import ETH, EUR
from tests.helpers.time_utils import DEFAULT_TIME_GEN, make_event

WALLET_ID = AccountChainId("wallet")


def test_fifo(acquisition_disposal_projector: AcquisitionDisposalProjector) -> None:
    t1_amount_bought = Decimal("1.0")
    t1_amount_spent = Decimal("2000")
    events = [
        make_event(
            legs=[
                LedgerLeg(asset_id=ETH, quantity=t1_amount_bought, account_chain_id=WALLET_ID),
                LedgerLeg(asset_id=EUR, quantity=-t1_amount_spent, account_chain_id=WALLET_ID),
            ],
        )
    ]

    t2_amount_bought = Decimal("0.5")
    t2_amount_spent = Decimal("2200")
    events.append(
        make_event(
            legs=[
                LedgerLeg(asset_id=ETH, quantity=t2_amount_bought, account_chain_id=WALLET_ID),
                LedgerLeg(asset_id=EUR, quantity=-t2_amount_spent, account_chain_id=WALLET_ID),
            ],
        )
    )

    t3_amount_spent = Decimal("0.6")
    t3_amount_bought = Decimal("2040")
    events.append(
        make_event(
            legs=[
                LedgerLeg(asset_id=ETH, quantity=-t3_amount_spent, account_chain_id=WALLET_ID),
                LedgerLeg(asset_id=EUR, quantity=t3_amount_bought, account_chain_id=WALLET_ID),
            ],
        )
    )

    t4_amount_spent = Decimal("0.7")
    t4_amount_bought = Decimal("1900")
    events.append(
        make_event(
            legs=[
                LedgerLeg(asset_id=ETH, quantity=-t4_amount_spent, account_chain_id=WALLET_ID),
                LedgerLeg(asset_id=EUR, quantity=t4_amount_bought, account_chain_id=WALLET_ID),
            ],
        )
    )

    result = acquisition_disposal_projector.project(events)

    assert len(result.acquisition_lots) == 2
    assert len(result.disposal_links) == 3

    lot_1 = result.acquisition_lots[0]
    assert lot_1.event_origin == events[0].event_origin
    assert lot_1.account_chain_id == WALLET_ID
    assert lot_1.asset_id == ETH
    assert lot_1.is_fee is False
    assert lot_1.timestamp == events[0].timestamp
    assert lot_1.quantity_acquired == t1_amount_bought
    assert lot_1.cost_per_unit == t1_amount_spent / t1_amount_bought

    lot_2 = result.acquisition_lots[1]
    assert lot_2.event_origin == events[1].event_origin
    assert lot_2.account_chain_id == WALLET_ID
    assert lot_2.asset_id == ETH
    assert lot_2.is_fee is False
    assert lot_2.timestamp == events[1].timestamp
    assert lot_2.quantity_acquired == t2_amount_bought
    assert lot_2.cost_per_unit == t2_amount_spent / t2_amount_bought

    dl_1 = result.disposal_links[0]
    assert dl_1.lot_id == lot_1.id
    assert dl_1.event_origin == events[2].event_origin
    assert dl_1.account_chain_id == WALLET_ID
    assert dl_1.asset_id == ETH
    assert dl_1.is_fee is False
    assert dl_1.timestamp == events[2].timestamp
    assert dl_1.quantity_used == t3_amount_spent
    assert dl_1.proceeds_total == t3_amount_bought

    dl_2 = result.disposal_links[1]
    assert dl_2.lot_id == lot_1.id
    assert dl_2.event_origin == events[3].event_origin
    assert dl_2.account_chain_id == WALLET_ID
    assert dl_2.asset_id == ETH
    assert dl_2.is_fee is False
    d2_expected_quantity = t1_amount_bought - t3_amount_spent
    assert dl_2.quantity_used == d2_expected_quantity
    assert dl_2.proceeds_total == d2_expected_quantity * (t4_amount_bought / t4_amount_spent)

    dl_3 = result.disposal_links[2]
    assert dl_3.lot_id == lot_2.id
    assert dl_3.event_origin == events[3].event_origin
    assert dl_3.account_chain_id == WALLET_ID
    assert dl_3.asset_id == ETH
    assert dl_3.is_fee is False
    d3_expected_quantity = t4_amount_spent - d2_expected_quantity
    assert dl_3.quantity_used == d3_expected_quantity
    assert dl_3.proceeds_total == d3_expected_quantity * (t4_amount_bought / t4_amount_spent)


def test_obtaining_price_from_provider(acquisition_disposal_projector: AcquisitionDisposalProjector) -> None:
    t1_amount_bought = Decimal("1.0")
    t1_amount_spent = Decimal("2000")
    events = [
        make_event(
            legs=[
                LedgerLeg(asset_id=ETH, quantity=t1_amount_bought, account_chain_id=WALLET_ID),
                LedgerLeg(asset_id=EUR, quantity=-t1_amount_spent, account_chain_id=WALLET_ID),
            ],
        )
    ]

    t2_time = DEFAULT_TIME_GEN.next()
    t2_amount_dropped = Decimal("0.6")
    t2_amount_fee = Decimal("0.0001")
    events.append(
        make_event(
            legs=[
                LedgerLeg(asset_id=AssetId("SPK"), quantity=t2_amount_dropped, account_chain_id=WALLET_ID),
                LedgerLeg(asset_id=ETH, quantity=-t2_amount_fee, account_chain_id=WALLET_ID, is_fee=True),
            ],
            timestamp=t2_time,
        )
    )

    result = acquisition_disposal_projector.project(events)

    assert len(result.acquisition_lots) == 2
    assert len(result.disposal_links) == 1

    lot_2 = result.acquisition_lots[1]
    assert lot_2.event_origin == events[1].event_origin
    assert lot_2.account_chain_id == WALLET_ID
    assert lot_2.asset_id == AssetId("SPK")
    assert lot_2.is_fee is False
    assert lot_2.timestamp == t2_time
    assert lot_2.quantity_acquired == t2_amount_dropped
    assert lot_2.cost_per_unit == acquisition_disposal_projector._price_provider.rate("SPK", "EUR", t2_time)

    disposal = result.disposal_links[0]
    assert disposal.event_origin == events[1].event_origin
    assert disposal.account_chain_id == WALLET_ID
    assert disposal.asset_id == ETH
    assert disposal.is_fee is True
    assert disposal.timestamp == t2_time
    assert disposal.quantity_used == t2_amount_fee
    fee_rate = acquisition_disposal_projector._price_provider.rate("ETH", "EUR", t2_time)
    assert disposal.proceeds_total == fee_rate * disposal.quantity_used


def test_transfers_dont_create_acquisition(
    acquisition_disposal_projector: AcquisitionDisposalProjector,
) -> None:
    hardware_wallet = AccountChainId("ledger")
    buy_amount = Decimal("1.5")
    transfer_amount = Decimal("0.5")
    buy_spent_eur = Decimal("3000")
    events = [
        make_event(
            legs=[
                LedgerLeg(asset_id=ETH, quantity=buy_amount, account_chain_id=KRAKEN_ACCOUNT_ID),
                LedgerLeg(asset_id=EUR, quantity=-buy_spent_eur, account_chain_id=KRAKEN_ACCOUNT_ID),
            ],
        ),
        make_event(
            legs=[
                LedgerLeg(asset_id=ETH, quantity=transfer_amount, account_chain_id=hardware_wallet),
                LedgerLeg(asset_id=ETH, quantity=-transfer_amount, account_chain_id=KRAKEN_ACCOUNT_ID),
            ],
        ),
    ]

    result = acquisition_disposal_projector.project(events)

    assert len(result.acquisition_lots) == 1
    acquisition_lot = result.acquisition_lots[0]
    assert acquisition_lot.event_origin == events[0].event_origin
    assert acquisition_lot.account_chain_id == KRAKEN_ACCOUNT_ID
    assert acquisition_lot.asset_id == ETH
    assert acquisition_lot.is_fee is False
    assert acquisition_lot.timestamp == events[0].timestamp
    assert acquisition_lot.quantity_acquired == buy_amount
    assert acquisition_lot.cost_per_unit == buy_spent_eur / buy_amount

    assert result.disposal_links == []


def test_disposal_without_acquisition_raises(acquisition_disposal_projector: AcquisitionDisposalProjector) -> None:
    events = [
        make_event(
            legs=[
                LedgerLeg(asset_id=ETH, quantity=Decimal("-1.0"), account_chain_id=WALLET_ID),
                LedgerLeg(asset_id=EUR, quantity=Decimal("2500"), account_chain_id=WALLET_ID),
            ],
        )
    ]

    with pytest.raises(AcquisitionDisposalProjectionError):
        acquisition_disposal_projector.project(events)
