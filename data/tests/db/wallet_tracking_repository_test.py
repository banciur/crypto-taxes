from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from accounts import KRAKEN_ACCOUNT_ID
from db.wallet_tracking import (
    WalletTrackingBalanceOrm,
    WalletTrackingIssueOrm,
    WalletTrackingRepository,
    WalletTrackingStateOrm,
)
from domain.ledger import EventLocation, EventOrigin
from domain.wallet_tracking import (
    WalletBalance,
    WalletTrackingIssue,
    WalletTrackingState,
    WalletTrackingStatus,
)
from tests.constants import BASE_WALLET, BTC, ETH, EUR, LEDGER_WALLET


def _origin(location: EventLocation, external_id: str) -> EventOrigin:
    return EventOrigin(location=location, external_id=external_id)


def _completed_state(*, balances: list[WalletBalance]) -> WalletTrackingState:
    return WalletTrackingState(
        status=WalletTrackingStatus.COMPLETED,
        failed_event=None,
        issues=[],
        balances=balances,
    )


def _failed_state() -> WalletTrackingState:
    attempted_eth = Decimal("-1.2")
    available_eth = Decimal("1.0")
    attempted_eur = Decimal("-5.5")
    available_eur = Decimal("5.0")
    return WalletTrackingState(
        status=WalletTrackingStatus.FAILED,
        failed_event=_origin(EventLocation.BASE, "evt-2"),
        issues=[
            WalletTrackingIssue(
                event=_origin(EventLocation.BASE, "evt-2"),
                account_chain_id=BASE_WALLET,
                asset_id=EUR,
                attempted_delta=attempted_eur,
                available_balance=available_eur,
                missing_balance=-(available_eur + attempted_eur),
            ),
            WalletTrackingIssue(
                event=_origin(EventLocation.BASE, "evt-2"),
                account_chain_id=KRAKEN_ACCOUNT_ID,
                asset_id=ETH,
                attempted_delta=attempted_eth,
                available_balance=available_eth,
                missing_balance=-(available_eth + attempted_eth),
            ),
        ],
        balances=[
            WalletBalance(
                account_chain_id=BASE_WALLET,
                asset_id=EUR,
                balance=available_eur,
            ),
            WalletBalance(
                account_chain_id=KRAKEN_ACCOUNT_ID,
                asset_id=ETH,
                balance=available_eth,
            ),
        ],
    )


@pytest.fixture()
def repo(test_session: Session) -> WalletTrackingRepository:
    return WalletTrackingRepository(test_session)


def test_get_returns_none_when_wallet_tracking_state_is_empty(repo: WalletTrackingRepository) -> None:
    assert repo.get() is None


def test_replace_persists_completed_state_with_deterministic_balance_order(
    repo: WalletTrackingRepository,
) -> None:
    kraken_eur = Decimal("1000")
    ledger_btc = Decimal("0.25")
    base_eth = Decimal("1.5")
    state = _completed_state(
        balances=[
            WalletBalance(account_chain_id=LEDGER_WALLET, asset_id=BTC, balance=ledger_btc),
            WalletBalance(account_chain_id=KRAKEN_ACCOUNT_ID, asset_id=EUR, balance=kraken_eur),
            WalletBalance(account_chain_id=BASE_WALLET, asset_id=ETH, balance=base_eth),
        ]
    )

    persisted = repo.replace(state)
    reloaded = repo.get()

    expected_balances = [
        WalletBalance(account_chain_id=BASE_WALLET, asset_id=ETH, balance=base_eth),
        WalletBalance(account_chain_id=LEDGER_WALLET, asset_id=BTC, balance=ledger_btc),
        WalletBalance(account_chain_id=KRAKEN_ACCOUNT_ID, asset_id=EUR, balance=kraken_eur),
    ]
    assert persisted == state
    assert reloaded == WalletTrackingState(
        status=WalletTrackingStatus.COMPLETED,
        failed_event=None,
        issues=[],
        balances=expected_balances,
    )


def test_replace_fully_replaces_prior_state(
    repo: WalletTrackingRepository,
    test_session: Session,
) -> None:
    repo.replace(_failed_state())

    final_balance = Decimal("2.0")
    replacement_state = WalletTrackingState(
        status=WalletTrackingStatus.COMPLETED,
        failed_event=None,
        issues=[],
        balances=[
            WalletBalance(
                account_chain_id=LEDGER_WALLET,
                asset_id=BTC,
                balance=final_balance,
            )
        ],
    )

    repo.replace(replacement_state)

    assert repo.get() == replacement_state
    state_rows = test_session.execute(select(WalletTrackingStateOrm)).scalars().all()
    balance_rows = test_session.execute(select(WalletTrackingBalanceOrm)).scalars().all()

    assert len(state_rows) == 1
    state_row = state_rows[0]
    assert state_row.singleton_id == 1
    assert state_row.status == WalletTrackingStatus.COMPLETED.value
    assert state_row.failed_origin_location is None
    assert state_row.failed_origin_external_id is None
    assert [(row.account_chain_id, row.asset_id, row.balance) for row in balance_rows] == [
        (LEDGER_WALLET, BTC, final_balance)
    ]
    assert test_session.execute(select(WalletTrackingIssueOrm)).scalars().all() == []


def test_replace_persists_failed_state_issues(repo: WalletTrackingRepository, test_session: Session) -> None:
    failed_state = _failed_state()

    persisted = repo.replace(failed_state)
    reloaded = repo.get()
    issue_rows = test_session.execute(select(WalletTrackingIssueOrm)).scalars().all()

    assert persisted == failed_state
    assert reloaded is not None
    assert reloaded.status == failed_state.status
    assert reloaded.failed_event == failed_state.failed_event
    assert {(issue.account_chain_id, issue.asset_id, issue.missing_balance) for issue in reloaded.issues} == {
        (BASE_WALLET, EUR, Decimal("0.5")),
        (KRAKEN_ACCOUNT_ID, ETH, Decimal("0.2")),
    }
    assert len(issue_rows) == len(failed_state.issues)
    assert all(row.id is not None for row in issue_rows)
