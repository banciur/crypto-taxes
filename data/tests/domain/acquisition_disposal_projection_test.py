from __future__ import annotations

from decimal import Decimal

import pytest

from accounts import KRAKEN_ACCOUNT_ID
from domain.acquisition_disposal_projection import (
    AcquisitionDisposalProjectionError,
    AcquisitionDisposalProjector,
)
from domain.ledger import AccountChainId, AssetId, LedgerLeg
from tests.constants import BTC, ETH, EUR
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


def test_transfer_with_explicit_fee_creates_only_fee_disposal(
    acquisition_disposal_projector: AcquisitionDisposalProjector,
) -> None:
    receiving_wallet = AccountChainId("ledger")
    acquired_btc = Decimal("1")
    spent_eur = Decimal("30000")
    transferred_btc = Decimal("0.99")
    fee_btc = Decimal("0.01")
    events = [
        make_event(
            legs=[
                LedgerLeg(asset_id=BTC, quantity=acquired_btc, account_chain_id=KRAKEN_ACCOUNT_ID),
                LedgerLeg(asset_id=EUR, quantity=-spent_eur, account_chain_id=KRAKEN_ACCOUNT_ID),
            ],
        ),
        make_event(
            legs=[
                LedgerLeg(asset_id=BTC, quantity=-transferred_btc, account_chain_id=KRAKEN_ACCOUNT_ID),
                LedgerLeg(asset_id=BTC, quantity=-fee_btc, account_chain_id=KRAKEN_ACCOUNT_ID, is_fee=True),
                LedgerLeg(asset_id=BTC, quantity=transferred_btc, account_chain_id=receiving_wallet),
            ],
        ),
    ]

    result = acquisition_disposal_projector.project(events)

    assert len(result.acquisition_lots) == 1
    assert len(result.disposal_links) == 1

    disposal = result.disposal_links[0]
    assert disposal.event_origin == events[1].event_origin
    assert disposal.account_chain_id == KRAKEN_ACCOUNT_ID
    assert disposal.asset_id == BTC
    assert disposal.is_fee is True
    assert disposal.quantity_used == fee_btc
    fee_rate = acquisition_disposal_projector._price_provider.rate(BTC, EUR, events[1].timestamp)
    assert disposal.proceeds_total == fee_rate * fee_btc


def test_transfer_without_explicit_fee_leg_projects_only_residual_disposal(
    acquisition_disposal_projector: AcquisitionDisposalProjector,
) -> None:
    receiving_wallet = AccountChainId("ledger")
    acquired_btc = Decimal("1")
    spent_eur = Decimal("30000")
    sent_btc = Decimal("1")
    received_btc = Decimal("0.99")
    residual_disposal = sent_btc - received_btc
    events = [
        make_event(
            legs=[
                LedgerLeg(asset_id=BTC, quantity=acquired_btc, account_chain_id=KRAKEN_ACCOUNT_ID),
                LedgerLeg(asset_id=EUR, quantity=-spent_eur, account_chain_id=KRAKEN_ACCOUNT_ID),
            ],
        ),
        make_event(
            legs=[
                LedgerLeg(asset_id=BTC, quantity=-sent_btc, account_chain_id=KRAKEN_ACCOUNT_ID),
                LedgerLeg(asset_id=BTC, quantity=received_btc, account_chain_id=receiving_wallet),
            ],
        ),
    ]

    result = acquisition_disposal_projector.project(events)

    assert len(result.acquisition_lots) == 1
    assert len(result.disposal_links) == 1

    disposal = result.disposal_links[0]
    assert disposal.event_origin == events[1].event_origin
    assert disposal.account_chain_id == KRAKEN_ACCOUNT_ID
    assert disposal.asset_id == BTC
    assert disposal.is_fee is False
    assert disposal.quantity_used == residual_disposal
    disposal_rate = acquisition_disposal_projector._price_provider.rate(BTC, EUR, events[1].timestamp)
    assert disposal.proceeds_total == disposal_rate * residual_disposal


def test_transfer_gain_creates_only_residual_acquisition(
    acquisition_disposal_projector: AcquisitionDisposalProjector,
) -> None:
    sending_wallet = AccountChainId("kraken")
    receiving_wallet = AccountChainId("ledger")
    sent_eth = Decimal("1")
    received_eth = Decimal("1.5")
    residual_acquisition = received_eth - sent_eth
    event = make_event(
        legs=[
            LedgerLeg(asset_id=ETH, quantity=-sent_eth, account_chain_id=sending_wallet),
            LedgerLeg(asset_id=ETH, quantity=received_eth, account_chain_id=receiving_wallet),
        ],
    )

    result = acquisition_disposal_projector.project([event])

    assert result.disposal_links == []
    assert len(result.acquisition_lots) == 1

    lot = result.acquisition_lots[0]
    assert lot.event_origin == event.event_origin
    assert lot.account_chain_id == receiving_wallet
    assert lot.asset_id == ETH
    assert lot.is_fee is False
    assert lot.quantity_acquired == residual_acquisition
    lot_rate = acquisition_disposal_projector._price_provider.rate(ETH, EUR, event.timestamp)
    assert lot.cost_per_unit == lot_rate


def test_positive_residual_is_split_proportionally_across_incoming_legs(
    acquisition_disposal_projector: AcquisitionDisposalProjector,
) -> None:
    sending_wallet = AccountChainId("kraken")
    first_receiving_wallet = AccountChainId("ledger")
    second_receiving_wallet = AccountChainId("trezor")
    sent_eth = Decimal("1")
    first_received_eth = Decimal("0.6")
    second_received_eth = Decimal("0.5")
    residual_acquisition = first_received_eth + second_received_eth - sent_eth
    first_expected_acquisition = residual_acquisition * first_received_eth / (first_received_eth + second_received_eth)
    second_expected_acquisition = residual_acquisition - first_expected_acquisition
    event = make_event(
        legs=[
            LedgerLeg(asset_id=ETH, quantity=-sent_eth, account_chain_id=sending_wallet),
            LedgerLeg(asset_id=ETH, quantity=first_received_eth, account_chain_id=first_receiving_wallet),
            LedgerLeg(asset_id=ETH, quantity=second_received_eth, account_chain_id=second_receiving_wallet),
        ],
    )

    result = acquisition_disposal_projector.project([event])

    assert result.disposal_links == []
    assert len(result.acquisition_lots) == 2

    first_lot, second_lot = result.acquisition_lots
    assert first_lot.account_chain_id == first_receiving_wallet
    assert first_lot.quantity_acquired == first_expected_acquisition
    assert second_lot.account_chain_id == second_receiving_wallet
    assert second_lot.quantity_acquired == second_expected_acquisition
    assert first_lot.quantity_acquired + second_lot.quantity_acquired == residual_acquisition


def test_negative_residual_is_split_proportionally_across_outgoing_legs(
    acquisition_disposal_projector: AcquisitionDisposalProjector,
) -> None:
    first_sending_wallet = AccountChainId("kraken")
    second_sending_wallet = AccountChainId("ledger")
    receiving_wallet = AccountChainId("trezor")
    acquired_eth = Decimal("2")
    spent_eur = Decimal("3000")
    first_sent_eth = Decimal("0.6")
    second_sent_eth = Decimal("0.5")
    received_eth = Decimal("0.6")
    residual_disposal = first_sent_eth + second_sent_eth - received_eth
    first_expected_disposal = residual_disposal * first_sent_eth / (first_sent_eth + second_sent_eth)
    second_expected_disposal = residual_disposal - first_expected_disposal
    events = [
        make_event(
            legs=[
                LedgerLeg(asset_id=ETH, quantity=acquired_eth, account_chain_id=WALLET_ID),
                LedgerLeg(asset_id=EUR, quantity=-spent_eur, account_chain_id=WALLET_ID),
            ],
        ),
        make_event(
            legs=[
                LedgerLeg(asset_id=ETH, quantity=-first_sent_eth, account_chain_id=first_sending_wallet),
                LedgerLeg(asset_id=ETH, quantity=-second_sent_eth, account_chain_id=second_sending_wallet),
                LedgerLeg(asset_id=ETH, quantity=received_eth, account_chain_id=receiving_wallet),
            ],
        ),
    ]

    result = acquisition_disposal_projector.project(events)

    assert len(result.disposal_links) == 2

    first_link, second_link = result.disposal_links
    assert first_link.account_chain_id == first_sending_wallet
    assert first_link.quantity_used == first_expected_disposal
    assert second_link.account_chain_id == second_sending_wallet
    assert second_link.quantity_used == second_expected_disposal
    assert first_link.quantity_used + second_link.quantity_used == residual_disposal


def test_sale_does_not_assign_trade_eur_proceeds_to_fee_disposal(
    acquisition_disposal_projector: AcquisitionDisposalProjector,
) -> None:
    acquired_btc = Decimal("1")
    spent_eur = Decimal("30000")
    sold_btc = Decimal("0.4")
    received_eur = Decimal("16000")
    fee_eth = Decimal("0.01")
    eth_bought = Decimal("1")
    eth_spent_eur = Decimal("1500")
    events = [
        make_event(
            legs=[
                LedgerLeg(asset_id=BTC, quantity=acquired_btc, account_chain_id=WALLET_ID),
                LedgerLeg(asset_id=EUR, quantity=-spent_eur, account_chain_id=WALLET_ID),
            ],
        ),
        make_event(
            legs=[
                LedgerLeg(asset_id=ETH, quantity=eth_bought, account_chain_id=WALLET_ID),
                LedgerLeg(asset_id=EUR, quantity=-eth_spent_eur, account_chain_id=WALLET_ID),
            ],
        ),
        make_event(
            legs=[
                LedgerLeg(asset_id=BTC, quantity=-sold_btc, account_chain_id=WALLET_ID),
                LedgerLeg(asset_id=EUR, quantity=received_eur, account_chain_id=WALLET_ID),
                LedgerLeg(asset_id=ETH, quantity=-fee_eth, account_chain_id=WALLET_ID, is_fee=True),
            ],
        ),
    ]

    result = acquisition_disposal_projector.project(events)

    assert len(result.disposal_links) == 2

    sale_disposal, fee_disposal = result.disposal_links
    assert sale_disposal.asset_id == BTC
    assert sale_disposal.is_fee is False
    assert sale_disposal.quantity_used == sold_btc
    assert sale_disposal.proceeds_total == received_eur

    assert fee_disposal.asset_id == ETH
    assert fee_disposal.is_fee is True
    assert fee_disposal.quantity_used == fee_eth
    fee_rate = acquisition_disposal_projector._price_provider.rate(ETH, EUR, events[2].timestamp)
    assert fee_disposal.proceeds_total == fee_rate * fee_eth


def test_residual_disposal_without_prior_lot_raises(
    acquisition_disposal_projector: AcquisitionDisposalProjector,
) -> None:
    sending_wallet = AccountChainId("kraken")
    receiving_wallet = AccountChainId("ledger")
    sent_btc = Decimal("1")
    received_btc = Decimal("0.99")
    event = make_event(
        legs=[
            LedgerLeg(asset_id=BTC, quantity=-sent_btc, account_chain_id=sending_wallet),
            LedgerLeg(asset_id=BTC, quantity=received_btc, account_chain_id=receiving_wallet),
        ],
    )

    with pytest.raises(AcquisitionDisposalProjectionError):
        acquisition_disposal_projector.project([event])


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
