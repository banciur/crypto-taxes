from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api.api as api
from accounts import AccountConfig, AccountRegistry
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
    assert response.json() == [
        {
            "account_chain_id": f"{EventLocation.BASE}:{address}",
            "name": "Main Wallet",
            "location": EventLocation.BASE,
            "address": address,
            "skip_sync": False,
        },
        {
            "account_chain_id": "coinbase",
            "name": "Coinbase",
            "location": EventLocation.COINBASE,
            "address": None,
            "skip_sync": False,
        },
        {
            "account_chain_id": "kraken",
            "name": "Kraken",
            "location": EventLocation.KRAKEN,
            "address": None,
            "skip_sync": False,
        },
    ]
