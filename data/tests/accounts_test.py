from __future__ import annotations

import json
from pathlib import Path

from accounts import load_accounts


def test_load_accounts_normalizes_address_and_chain_types(tmp_path: Path) -> None:
    address = "0xAbCdEf"
    chain = "eth"
    accounts_path = tmp_path / "accounts.json"
    accounts_path.write_text(json.dumps([{"address": address, "chains": [chain]}]))

    loaded_accounts = load_accounts(accounts_path)

    assert len(loaded_accounts) == 1
    loaded_account = loaded_accounts[0]
    assert loaded_account.address == address.lower()
    assert loaded_account.chains == [chain]


def test_load_accounts_dedupes_account_chain_pairs(tmp_path: Path) -> None:
    first_address = "0xAbCdEf"
    second_address = "0x987654"
    eth_chain = "eth"
    arb_chain = "arbitrum"
    accounts_path = tmp_path / "accounts.json"
    accounts_path.write_text(
        json.dumps(
            [
                {"address": first_address, "chains": [eth_chain, eth_chain]},
                {"address": first_address.lower(), "chains": [arb_chain]},
                {"address": second_address, "chains": [arb_chain, arb_chain]},
            ]
        )
    )

    loaded_accounts = load_accounts(accounts_path)

    assert len(loaded_accounts) == 2
    first_loaded = loaded_accounts[0]
    second_loaded = loaded_accounts[1]
    assert first_loaded.address == first_address.lower()
    assert first_loaded.chains == [eth_chain, arb_chain]
    assert second_loaded.address == second_address.lower()
    assert second_loaded.chains == [arb_chain]
