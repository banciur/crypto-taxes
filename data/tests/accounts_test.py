from __future__ import annotations

import json
from pathlib import Path

import pytest

from accounts import AccountConfig, AccountRegistry, load_accounts, location_address_from_account_chain_id
from domain.ledger import EventLocation, WalletAddress
from tests.constants import ETH_ADDRESS, LOCATION


def test_load_accounts_normalizes_address_and_location_types(tmp_path: Path) -> None:
    name = "Main Wallet"
    skip_sync = False
    accounts_path = tmp_path / "accounts.json"
    accounts_path.write_text(
        json.dumps(
            [
                {
                    "name": name,
                    "address": ETH_ADDRESS.upper(),
                    "locations": [LOCATION.value.lower()],
                    "skip_sync": skip_sync,
                }
            ]
        )
    )

    loaded_accounts = load_accounts(accounts_path)

    assert len(loaded_accounts) == 1
    loaded_account = loaded_accounts[0]
    assert loaded_account.name == name
    assert loaded_account.address == ETH_ADDRESS
    assert loaded_account.locations == {LOCATION}
    assert loaded_account.skip_sync is skip_sync


def test_account_config_requires_preparsed_locations() -> None:
    with pytest.raises(Exception):
        AccountConfig.model_validate(
            {
                "name": "Wallet",
                "address": WalletAddress("0xabc"),
                "locations": ["ethereum"],
                "skip_sync": False,
            }
        )


def test_load_accounts_raises_for_duplicate_address(tmp_path: Path) -> None:
    accounts_path = tmp_path / "accounts.json"
    accounts_path.write_text(
        json.dumps(
            [
                {
                    "name": "Primary",
                    "address": ETH_ADDRESS.upper(),
                    "locations": [EventLocation.BASE.value.lower()],
                    "skip_sync": False,
                },
                {
                    "name": "Primary",
                    "address": ETH_ADDRESS.lower(),
                    "locations": [EventLocation.ETHEREUM.value.lower()],
                    "skip_sync": False,
                },
            ]
        )
    )

    with pytest.raises(ValueError, match="Duplicate address"):
        load_accounts(accounts_path)


def test_load_accounts_defaults_skip_sync_to_false_when_omitted(tmp_path: Path) -> None:
    accounts_path = tmp_path / "accounts.json"
    accounts_path.write_text(
        json.dumps(
            [
                {
                    "name": "Primary",
                    "address": ETH_ADDRESS.upper(),
                    "locations": [LOCATION.value.lower()],
                }
            ]
        )
    )

    loaded_accounts = load_accounts(accounts_path)

    assert len(loaded_accounts) == 1
    assert loaded_accounts[0].skip_sync is False


def test_registry_resolves_owned_account_chain_ids(tmp_path: Path) -> None:
    accounts_path = tmp_path / "accounts.json"
    accounts_path.write_text(
        json.dumps(
            [
                {
                    "name": "Primary",
                    "address": ETH_ADDRESS.upper(),
                    "locations": [LOCATION.value.lower()],
                    "skip_sync": False,
                }
            ]
        )
    )

    accounts = load_accounts(accounts_path)
    registry = AccountRegistry(accounts)
    resolved = registry.resolve_owned_id(
        location=LOCATION,
        address=ETH_ADDRESS,
    )

    assert resolved is not None
    assert str(resolved) == f"{LOCATION}:{ETH_ADDRESS}"
    assert registry.is_owned(resolved)
    assert registry.name_for(resolved) == "Primary"
    assert location_address_from_account_chain_id(resolved) == (
        LOCATION,
        ETH_ADDRESS,
    )
