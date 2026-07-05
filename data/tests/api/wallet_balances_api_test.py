from collections.abc import Callable
from decimal import Decimal
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from db.wallet_projection import WalletBalanceRepository
from domain.wallet_projection import WalletBalance
from tests.constants import BASE_WALLET, BTC


@pytest.fixture()
def persist_wallet_balances(client: TestClient) -> Callable[[list[WalletBalance]], None]:
    def persist(balances: list[WalletBalance]) -> None:
        app = cast(FastAPI, client.app)
        with app.state.sessionmaker() as session:
            WalletBalanceRepository(session).replace(balances)

    return persist


def test_get_wallet_balances_returns_empty_list_when_no_balances_are_persisted(client: TestClient) -> None:
    response = client.get("/wallet-balances")

    assert response.status_code == 200
    assert response.json() == []


def test_get_wallet_balances_returns_persisted_balances(
    client: TestClient,
    persist_wallet_balances: Callable[[list[WalletBalance]], None],
) -> None:
    balance = WalletBalance(account_chain_id=BASE_WALLET, asset_id=BTC, balance=Decimal("0.25"))
    persist_wallet_balances([balance])

    response = client.get("/wallet-balances")

    assert response.status_code == 200
    assert response.json() == [
        {
            "account_chain_id": balance.account_chain_id,
            "asset_id": balance.asset_id,
            "balance": str(balance.balance),
        }
    ]
