from decimal import Decimal

import pytest

from domain.wallet_balance_tracker import WalletBalanceError, WalletBalanceTracker
from tests.constants import BTC, ETH, KRAKEN_WALLET, LEDGER_WALLET, OUTSIDE_WALLET, SPOT_WALLET


def test_wallet_balance_tracker_updates_balances() -> None:
    tracker = WalletBalanceTracker()
    asset_id = ETH
    wallet_id = KRAKEN_WALLET

    starting_quantity = Decimal("1.5")
    tracker.apply_movement(asset_id=asset_id, wallet_id=wallet_id, quantity=starting_quantity)

    reduction = Decimal("0.4")
    tracker.apply_movement(asset_id=asset_id, wallet_id=wallet_id, quantity=-reduction)

    expected_balance = starting_quantity - reduction
    assert tracker.get_balance(asset_id=asset_id, wallet_id=wallet_id) == expected_balance
    assert tracker.has_available(asset_id=asset_id, wallet_id=wallet_id, quantity=expected_balance)
    assert not tracker.has_available(asset_id=asset_id, wallet_id=wallet_id, quantity=expected_balance + Decimal("0.1"))

    with pytest.raises(WalletBalanceError):
        tracker.apply_movement(
            asset_id=asset_id,
            wallet_id=wallet_id,
            quantity=-(expected_balance + Decimal("0.01")),
        )


def test_asset_balances_for_filters_wallets() -> None:
    tracker = WalletBalanceTracker()

    eth_kraken = Decimal("1.2")
    eth_spot = Decimal("0.8")
    btc_kraken = Decimal("0.2")

    # "My" wallets
    tracker.apply_movement(asset_id=ETH, wallet_id=KRAKEN_WALLET, quantity=eth_kraken)
    tracker.apply_movement(asset_id=ETH, wallet_id=SPOT_WALLET, quantity=eth_spot)
    tracker.apply_movement(asset_id=BTC, wallet_id=KRAKEN_WALLET, quantity=btc_kraken)

    # "Other" wallets"
    tracker.apply_movement(asset_id=ETH, wallet_id=OUTSIDE_WALLET, quantity=Decimal("0.3"))
    tracker.apply_movement(asset_id=BTC, wallet_id=LEDGER_WALLET, quantity=Decimal("0.5"))

    totals = tracker.asset_balances_for({KRAKEN_WALLET, SPOT_WALLET})

    assert totals[ETH] == eth_kraken + eth_spot
    assert totals[BTC] == btc_kraken
