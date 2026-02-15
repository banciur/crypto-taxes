from __future__ import annotations

import json
from pathlib import Path

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


def test_load_accounts_dedupes_account_chain_pairs(tmp_path: Path) -> None:
    first_address = "0xAbCdEf"
    second_address = "0x987654"
    eth_chain = "eth"
    arb_chain = "arbitrum"
    accounts_path = tmp_path / "accounts.json"
    accounts_path.write_text(
        json.dumps(
            [
                {"name": "Primary", "address": first_address, "chains": [eth_chain, eth_chain], "skip_sync": False},
                {"name": "Primary", "address": first_address.lower(), "chains": [arb_chain], "skip_sync": False},
                {"name": "Dormant", "address": second_address, "chains": [arb_chain, arb_chain], "skip_sync": True},
            ]
        )
    )

    loaded_accounts = load_accounts(accounts_path)

    assert len(loaded_accounts) == 2
    first_loaded = loaded_accounts[0]
    second_loaded = loaded_accounts[1]
    assert first_loaded.name == "Primary"
    assert first_loaded.address == first_address.lower()
    assert first_loaded.chains == [eth_chain, arb_chain]
    assert first_loaded.skip_sync is False
    assert second_loaded.name == "Dormant"
    assert second_loaded.address == second_address.lower()
    assert second_loaded.chains == [arb_chain]
    assert second_loaded.skip_sync is True
