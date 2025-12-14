from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import DefaultDict

from domain.base_types import AssetId, WalletId

WalletBalances = DefaultDict[WalletId, Decimal]
AssetBalances = DefaultDict[AssetId, WalletBalances]


class WalletBalanceError(Exception):
    def __init__(
        self,
        *,
        asset_id: AssetId,
        wallet_id: WalletId,
        attempted_quantity: Decimal,
        available_balance: Decimal,
    ) -> None:
        self.asset_id = asset_id
        self.wallet_id = wallet_id
        self.attempted_quantity = attempted_quantity
        self.available_balance = available_balance
        message = (
            f"Insufficient balance for asset={asset_id} wallet={wallet_id} "
            f"attempted={attempted_quantity} available={available_balance}"
        )
        super().__init__(message)


class WalletBalanceTracker:
    def __init__(self) -> None:
        self._balances: AssetBalances = defaultdict(lambda: defaultdict(lambda: Decimal(0)))

    def apply_movement(self, *, asset_id: AssetId, wallet_id: WalletId, quantity: Decimal) -> None:
        current_balance = self._balances[asset_id][wallet_id]
        new_balance = current_balance + quantity
        if new_balance < 0:
            raise WalletBalanceError(
                asset_id=asset_id,
                wallet_id=wallet_id,
                attempted_quantity=quantity,
                available_balance=current_balance,
            )
        self._balances[asset_id][wallet_id] = new_balance

    def get_balance(self, *, asset_id: AssetId, wallet_id: WalletId) -> Decimal:
        return self._balances[asset_id][wallet_id]

    def has_available(self, *, asset_id: AssetId, wallet_id: WalletId, quantity: Decimal) -> bool:
        return self._balances[asset_id][wallet_id] >= quantity

    def asset_balances_for(self, wallet_ids: set[WalletId] | None = None) -> dict[AssetId, Decimal]:
        """Return per-asset totals limited to the provided wallets; None includes all wallets."""
        totals: dict[AssetId, Decimal] = {}
        for asset_id, wallet_balances in self._balances.items():
            total = sum(
                (
                    balance
                    for wallet_id, balance in wallet_balances.items()
                    if wallet_ids is None or wallet_id in wallet_ids
                ),
                start=Decimal(0),
            )
            totals[asset_id] = total
        return totals
