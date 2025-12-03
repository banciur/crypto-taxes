from __future__ import annotations

from collections import defaultdict
from decimal import Decimal


class WalletBalanceError(Exception):
    def __init__(
        self,
        *,
        asset_id: str,
        wallet_id: str,
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
        self._balances: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: Decimal(0)))

    def apply_movement(self, *, asset_id: str, wallet_id: str, quantity: Decimal) -> None:
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

    def get_balance(self, *, asset_id: str, wallet_id: str) -> Decimal:
        return self._balances[asset_id][wallet_id]

    def has_available(self, *, asset_id: str, wallet_id: str, quantity: Decimal) -> bool:
        return self._balances[asset_id][wallet_id] >= quantity

    def asset_balances_for(self, wallet_ids: set[str] | None = None) -> dict[str, Decimal]:
        totals: dict[str, Decimal] = {}
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
