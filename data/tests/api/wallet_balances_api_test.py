from collections.abc import Callable
from decimal import Decimal
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from db.wallet_projection import WalletProjectionRepository
from domain.projection import ProjectionStatus
from domain.wallet_projection import WalletBalance, WalletTrackingState
from tests.constants import BASE_WALLET, BTC


@pytest.fixture()
def persist_wallet_tracking_state(client: TestClient) -> Callable[[WalletTrackingState], None]:
    def persist(state: WalletTrackingState) -> None:
        app = cast(FastAPI, client.app)
        with app.state.sessionmaker() as session:
            WalletProjectionRepository(session).replace(state)

    return persist


def test_get_wallet_balances_returns_empty_list_when_state_is_missing(client: TestClient) -> None:
    response = client.get("/wallet-balances")

    assert response.status_code == 200
    assert response.json() == []


def test_get_wallet_balances_returns_persisted_balances(
    client: TestClient,
    persist_wallet_tracking_state: Callable[[WalletTrackingState], None],
) -> None:
    balance = WalletBalance(account_chain_id=BASE_WALLET, asset_id=BTC, balance=Decimal("0.25"))
    persist_wallet_tracking_state(
        WalletTrackingState(
            status=ProjectionStatus.COMPLETED,
            issues=[],
            balances=[balance],
        )
    )

    response = client.get("/wallet-balances")

    assert response.status_code == 200
    assert response.json() == [
        {
            "account_chain_id": balance.account_chain_id,
            "asset_id": balance.asset_id,
            "balance": str(balance.balance),
        }
    ]
