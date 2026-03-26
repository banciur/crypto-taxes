from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Iterable

from pydantic_base import StrictBaseModel

from .ledger import AccountChainId, AssetId, EventOrigin, LedgerEvent


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
        raise NotImplementedError

    def _assert_processing_order(self, previous: LedgerEvent | None, current: LedgerEvent) -> None:
        raise NotImplementedError

    def _net_event_deltas(self, event: LedgerEvent) -> dict[tuple[AccountChainId, AssetId], Decimal]:
        raise NotImplementedError

    def _validate_event(
        self,
        event: LedgerEvent,
        deltas: dict[tuple[AccountChainId, AssetId], Decimal],
        balances: dict[tuple[AccountChainId, AssetId], Decimal],
    ) -> list[WalletTrackingIssue]:
        raise NotImplementedError

    def _state_balances(
        self,
        balances: dict[tuple[AccountChainId, AssetId], Decimal],
    ) -> list[WalletBalance]:
        raise NotImplementedError
