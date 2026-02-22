from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import DefaultDict

from domain.ledger import AccountId, AssetId

AccountBalances = DefaultDict[AccountId, Decimal]
AssetBalances = DefaultDict[AssetId, AccountBalances]


class WalletBalanceError(Exception):
    def __init__(
        self,
        *,
        asset_id: AssetId,
        account_id: AccountId,
        attempted_quantity: Decimal,
        available_balance: Decimal,
    ) -> None:
        self.asset_id = asset_id
        self.account_id = account_id
        self.attempted_quantity = attempted_quantity
        self.available_balance = available_balance
        message = (
            f"Insufficient balance for asset={asset_id} account={account_id} "
            f"attempted={attempted_quantity} available={available_balance}"
        )
        super().__init__(message)


class WalletBalanceTracker:
    def __init__(self) -> None:
        self._balances: AssetBalances = defaultdict(lambda: defaultdict(lambda: Decimal(0)))

    def apply_movement(self, *, asset_id: AssetId, account_id: AccountId, quantity: Decimal) -> None:
        current_balance = self._balances[asset_id][account_id]
        new_balance = current_balance + quantity
        if new_balance < 0:
            raise WalletBalanceError(
                asset_id=asset_id,
                account_id=account_id,
                attempted_quantity=quantity,
                available_balance=current_balance,
            )
        self._balances[asset_id][account_id] = new_balance

    def get_balance(self, *, asset_id: AssetId, account_id: AccountId) -> Decimal:
        return self._balances[asset_id][account_id]

    def has_available(self, *, asset_id: AssetId, account_id: AccountId, quantity: Decimal) -> bool:
        return self._balances[asset_id][account_id] >= quantity

    def asset_balances_for(self, account_ids: set[AccountId] | None = None) -> dict[AssetId, Decimal]:
        """Return per-asset totals limited to the provided accounts; None includes all accounts."""
        totals: dict[AssetId, Decimal] = {}
        for asset_id, account_balances in self._balances.items():
            total = sum(
                (
                    balance
                    for account_id, balance in account_balances.items()
                    if account_ids is None or account_id in account_ids
                ),
                start=Decimal(0),
            )
            totals[asset_id] = total
        return totals
