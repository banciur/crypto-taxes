from __future__ import annotations

from decimal import Decimal

from accounts import KRAKEN_ACCOUNT_ID
from domain.ledger import LedgerLeg
from domain.wallet_projection import WalletProjector, WalletTrackingStatus
from tests.constants import BASE_WALLET, ETH, EUR, LEDGER_WALLET
from tests.helpers.time_utils import make_event


def test_wallet_projector_processes_events_across_multiple_accounts(
    wallet_projector: WalletProjector,
) -> None:
    starting_eur = Decimal("5000")
    acquired_eth = Decimal("1.5")
    spent_eur = Decimal("3000")
    transfer_eth = Decimal("0.4")
    fee_eur = Decimal("10")
    received_eur = Decimal("1200")
    sold_eth = Decimal("0.3")

    events = [
        make_event(legs=[LedgerLeg(asset_id=EUR, quantity=starting_eur, account_chain_id=KRAKEN_ACCOUNT_ID)]),
        make_event(
            legs=[
                LedgerLeg(asset_id=ETH, quantity=acquired_eth, account_chain_id=KRAKEN_ACCOUNT_ID),
                LedgerLeg(asset_id=EUR, quantity=-spent_eur, account_chain_id=KRAKEN_ACCOUNT_ID),
            ]
        ),
        make_event(
            legs=[
                LedgerLeg(asset_id=ETH, quantity=-transfer_eth, account_chain_id=KRAKEN_ACCOUNT_ID),
                LedgerLeg(asset_id=ETH, quantity=transfer_eth, account_chain_id=LEDGER_WALLET),
            ]
        ),
        make_event(
            legs=[
                LedgerLeg(asset_id=ETH, quantity=-sold_eth, account_chain_id=LEDGER_WALLET),
                LedgerLeg(asset_id=EUR, quantity=received_eur, account_chain_id=LEDGER_WALLET),
                LedgerLeg(asset_id=EUR, quantity=-fee_eur, account_chain_id=LEDGER_WALLET, is_fee=True),
            ]
        ),
    ]

    result = wallet_projector.project(events)

    expected_ledger_eth = transfer_eth - sold_eth
    expected_kraken_eth = acquired_eth - transfer_eth
    expected_ledger_eur = received_eur - fee_eur
    expected_kraken_eur = starting_eur - spent_eur

    assert result.status == WalletTrackingStatus.COMPLETED
    assert result.failed_event is None
    assert result.issues == []
    assert len(result.balances) == 4
    assert [(balance.account_chain_id, balance.asset_id, balance.balance) for balance in result.balances] == [
        (LEDGER_WALLET, ETH, expected_ledger_eth),
        (LEDGER_WALLET, EUR, expected_ledger_eur),
        (KRAKEN_ACCOUNT_ID, ETH, expected_kraken_eth),
        (KRAKEN_ACCOUNT_ID, EUR, expected_kraken_eur),
    ]


def test_wallet_projector_nets_same_event_deltas_across_distinct_leg_identities(
    wallet_projector: WalletProjector,
) -> None:
    starting_quantity = Decimal("1.0")
    received_quantity = Decimal("0.3")
    spent_quantity = Decimal("1.2")
    remaining_quantity = starting_quantity + received_quantity - spent_quantity

    events = [
        make_event(legs=[LedgerLeg(asset_id=ETH, quantity=starting_quantity, account_chain_id=KRAKEN_ACCOUNT_ID)]),
        make_event(
            legs=[
                LedgerLeg(asset_id=ETH, quantity=received_quantity, account_chain_id=KRAKEN_ACCOUNT_ID),
                LedgerLeg(
                    asset_id=ETH,
                    quantity=-spent_quantity,
                    account_chain_id=KRAKEN_ACCOUNT_ID,
                    is_fee=True,
                ),
            ]
        ),
    ]

    result = wallet_projector.project(events)

    assert result.status == WalletTrackingStatus.COMPLETED
    assert result.issues == []
    assert len(result.balances) == 1
    balance = result.balances[0]
    assert balance.account_chain_id == KRAKEN_ACCOUNT_ID
    assert balance.asset_id == ETH
    assert balance.balance == remaining_quantity


def test_wallet_projector_failure_is_event_atomic(wallet_projector: WalletProjector) -> None:
    starting_quantity = Decimal("1.0")
    attempted_quantity = Decimal("1.5")
    missing_quantity = attempted_quantity - starting_quantity
    events = [
        make_event(legs=[LedgerLeg(asset_id=ETH, quantity=starting_quantity, account_chain_id=KRAKEN_ACCOUNT_ID)]),
        make_event(
            legs=[
                LedgerLeg(asset_id=ETH, quantity=-attempted_quantity, account_chain_id=KRAKEN_ACCOUNT_ID),
                LedgerLeg(asset_id=ETH, quantity=attempted_quantity, account_chain_id=LEDGER_WALLET),
            ]
        ),
    ]

    result = wallet_projector.project(events)

    assert result.status == WalletTrackingStatus.FAILED
    assert result.failed_event == events[1].event_origin
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.event == events[1].event_origin
    assert issue.account_chain_id == KRAKEN_ACCOUNT_ID
    assert issue.asset_id == ETH
    assert issue.attempted_delta == -attempted_quantity
    assert issue.available_balance == starting_quantity
    assert issue.missing_balance == missing_quantity
    assert [(balance.account_chain_id, balance.asset_id, balance.balance) for balance in result.balances] == [
        (KRAKEN_ACCOUNT_ID, ETH, starting_quantity)
    ]


def test_wallet_projector_collects_all_blocking_issues_from_failed_event(
    wallet_projector: WalletProjector,
) -> None:
    eth_available = Decimal("1.0")
    eur_available = Decimal("5.0")
    eth_attempted = Decimal("1.2")
    eur_attempted = Decimal("7.0")
    events = [
        make_event(
            legs=[
                LedgerLeg(asset_id=ETH, quantity=eth_available, account_chain_id=KRAKEN_ACCOUNT_ID),
                LedgerLeg(asset_id=EUR, quantity=eur_available, account_chain_id=BASE_WALLET),
            ]
        ),
        make_event(
            legs=[
                LedgerLeg(asset_id=ETH, quantity=-eth_attempted, account_chain_id=KRAKEN_ACCOUNT_ID),
                LedgerLeg(asset_id=EUR, quantity=-eur_attempted, account_chain_id=BASE_WALLET),
            ]
        ),
    ]

    result = wallet_projector.project(events)

    assert result.status == WalletTrackingStatus.FAILED
    assert result.failed_event == events[1].event_origin
    assert [(issue.account_chain_id, issue.asset_id, issue.missing_balance) for issue in result.issues] == [
        (BASE_WALLET, EUR, eur_attempted - eur_available),
        (KRAKEN_ACCOUNT_ID, ETH, eth_attempted - eth_available),
    ]


def test_wallet_projector_excludes_zero_balances(wallet_projector: WalletProjector) -> None:
    acquired_quantity = Decimal("2.0")
    disposed_quantity = acquired_quantity
    events = [
        make_event(legs=[LedgerLeg(asset_id=ETH, quantity=acquired_quantity, account_chain_id=KRAKEN_ACCOUNT_ID)]),
        make_event(legs=[LedgerLeg(asset_id=ETH, quantity=-disposed_quantity, account_chain_id=KRAKEN_ACCOUNT_ID)]),
    ]

    result = wallet_projector.project(events)

    assert result.status == WalletTrackingStatus.COMPLETED
    assert result.balances == []
