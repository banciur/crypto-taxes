from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api.api as api
from accounts import (
    COINBASE_ACCOUNT_ID,
    COINBASE_ACCOUNT_NAME,
    KRAKEN_ACCOUNT_ID,
    KRAKEN_ACCOUNT_NAME,
    AccountConfig,
    AccountRegistry,
)
from domain.ledger import EventLocation, WalletAddress


def test_get_accounts_returns_merged_wallet_and_system_accounts(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    address = WalletAddress("0x4838b106fce9647bdf1e7877bf73ce8b0bad5f97")
    registry = AccountRegistry(
        [
            AccountConfig(
                name="Main Wallet",
                address=address,
                locations=frozenset({EventLocation.BASE}),
                skip_sync=False,
            )
        ]
    )

    monkeypatch.setattr(
        api.AccountRegistry,
        "from_path",
        classmethod(lambda cls, path=Path(): registry),
    )

    response = client.get("/accounts")

    assert response.status_code == 200
    assert {account["account_chain_id"]: account for account in response.json()} == {
        f"{EventLocation.BASE}:{address}": {
            "account_chain_id": f"{EventLocation.BASE}:{address}",
            "name": "Main Wallet",
            "skip_sync": False,
        },
        COINBASE_ACCOUNT_ID: {
            "account_chain_id": COINBASE_ACCOUNT_ID,
            "name": COINBASE_ACCOUNT_NAME,
            "skip_sync": False,
        },
        KRAKEN_ACCOUNT_ID: {
            "account_chain_id": KRAKEN_ACCOUNT_ID,
            "name": KRAKEN_ACCOUNT_NAME,
            "skip_sync": False,
        },
    }
