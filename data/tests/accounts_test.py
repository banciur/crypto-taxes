# Completely vibed didn't even read the code. Review during the next update
from __future__ import annotations

import json
from pathlib import Path

import pytest

from accounts import load_accounts


def test_load_accounts_normalizes_address_and_chain_types(tmp_path: Path) -> None:
    name = "Main Wallet"
    address = "0xAbCdEf"
    chain = "eth"
    skip_sync = False
    accounts_path = tmp_path / "accounts.json"
    accounts_path.write_text(
        json.dumps(
            [
                {
                    "name": name,
                    "address": address,
                    "chains": [chain],
                    "skip_sync": skip_sync,
                }
            ]
        )
    )

    loaded_accounts = load_accounts(accounts_path)

    assert len(loaded_accounts) == 1
    loaded_account = loaded_accounts[0]
    assert loaded_account.name == name
    assert loaded_account.address == address.lower()
    assert loaded_account.chains == [chain]
    assert loaded_account.skip_sync is skip_sync


def test_load_accounts_raises_for_duplicate_address(tmp_path: Path) -> None:
    first_address = "0xAbCdEf"
    eth_chain = "eth"
    arb_chain = "arbitrum"
    accounts_path = tmp_path / "accounts.json"
    accounts_path.write_text(
        json.dumps(
            [
                {"name": "Primary", "address": first_address, "chains": [eth_chain], "skip_sync": False},
                {"name": "Primary", "address": first_address.lower(), "chains": [arb_chain], "skip_sync": False},
            ]
        )
    )

    with pytest.raises(ValueError, match="Duplicate address"):
        load_accounts(accounts_path)
