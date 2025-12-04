from decimal import Decimal

import pytest

from domain.wallet_balance_tracker import WalletBalanceError, WalletBalanceTracker
from tests.constants import ETH, KRAKEN_WALLET


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
