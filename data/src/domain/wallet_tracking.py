from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Iterable

from pydantic_base import StrictBaseModel

from .ledger import AccountChainId, AssetId, EventOrigin, LedgerEvent

BalanceKey = tuple[AccountChainId, AssetId]
ZERO = Decimal(0)


class WalletTrackingStatus(StrEnum):
    NOT_RUN = "NOT_RUN"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class WalletBalance(StrictBaseModel):
    account_chain_id: AccountChainId
    asset_id: AssetId
    balance: Decimal


class WalletTrackingIssue(StrictBaseModel):
    event: EventOrigin
    account_chain_id: AccountChainId
    asset_id: AssetId
    attempted_delta: Decimal
    available_balance: Decimal
    missing_balance: Decimal


class WalletTrackingState(StrictBaseModel):
    status: WalletTrackingStatus
    processed_event_count: int
    last_applied_event: EventOrigin | None = None
    failed_event: EventOrigin | None = None
    issues: list[WalletTrackingIssue]
    balances: list[WalletBalance]


class WalletProjector:
    def project(self, events: Iterable[LedgerEvent]) -> WalletTrackingState:
        balances: dict[BalanceKey, Decimal] = {}
        processed_event_count = 0
        last_applied_event: EventOrigin | None = None

        for event in events:
            deltas = self._net_event_deltas(event)
            if issues := self._validate_event(event, deltas, balances):
                return WalletTrackingState(
                    status=WalletTrackingStatus.FAILED,
                    processed_event_count=processed_event_count,
                    last_applied_event=last_applied_event,
                    failed_event=event.event_origin,
                    issues=issues,
                    balances=self._state_balances(balances),
                )

            for key, delta in deltas.items():
                next_balance = balances.get(key, ZERO) + delta
                if next_balance == ZERO:
                    balances.pop(key, None)
                    continue
                balances[key] = next_balance

            processed_event_count += 1
            last_applied_event = event.event_origin

        return WalletTrackingState(
            status=WalletTrackingStatus.COMPLETED,
            processed_event_count=processed_event_count,
            last_applied_event=last_applied_event,
            failed_event=None,
            issues=[],
            balances=self._state_balances(balances),
        )

    @staticmethod
    def _net_event_deltas(event: LedgerEvent) -> dict[BalanceKey, Decimal]:
        deltas: dict[BalanceKey, Decimal] = {}
        for leg in event.legs:
            key = (leg.account_chain_id, leg.asset_id)
            deltas[key] = deltas.get(key, ZERO) + leg.quantity

        return {key: delta for key, delta in deltas.items() if delta != ZERO}

    @staticmethod
    def _validate_event(
        event: LedgerEvent,
        deltas: dict[BalanceKey, Decimal],
        balances: dict[BalanceKey, Decimal],
    ) -> list[WalletTrackingIssue]:
        issues: list[WalletTrackingIssue] = []

        for (account_chain_id, asset_id), attempted_delta in sorted(deltas.items()):
            if attempted_delta >= ZERO:
                continue

            available_balance = balances.get((account_chain_id, asset_id), ZERO)
            missing_balance = -(available_balance + attempted_delta)
            if missing_balance <= ZERO:
                continue

            issues.append(
                WalletTrackingIssue(
                    event=event.event_origin,
                    account_chain_id=account_chain_id,
                    asset_id=asset_id,
                    attempted_delta=attempted_delta,
                    available_balance=available_balance,
                    missing_balance=missing_balance,
                )
            )

        return issues

    def _state_balances(
        self,
        balances: dict[BalanceKey, Decimal],
    ) -> list[WalletBalance]:
        return [
            WalletBalance(
                account_chain_id=account_chain_id,
                asset_id=asset_id,
                balance=balance,
            )
            for (account_chain_id, asset_id), balance in sorted(balances.items())
            if balance != ZERO
        ]
