from __future__ import annotations

import json
from pathlib import Path

import pytest

from accounts import (
    COINBASE_ACCOUNT_ID,
    COINBASE_ACCOUNT_NAME,
    KRAKEN_ACCOUNT_ID,
    KRAKEN_ACCOUNT_NAME,
    AccountConfig,
    AccountRecord,
    AccountRegistry,
    account_chain_id_for,
    load_accounts,
    location_address_from_account_chain_id,
)
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
    assert registry.display_name_for(resolved) == "Primary"
    assert location_address_from_account_chain_id(resolved) == (
        LOCATION,
        ETH_ADDRESS,
    )


def test_registry_includes_default_system_accounts() -> None:
    address = WalletAddress("0x4838b106fce9647bdf1e7877bf73ce8b0bad5f97")
    wallet_account = AccountConfig(
        name="Primary",
        address=address,
        locations=frozenset({EventLocation.BASE}),
        skip_sync=False,
    )

    registry = AccountRegistry([wallet_account])

    assert registry.display_name_for(COINBASE_ACCOUNT_ID) == COINBASE_ACCOUNT_NAME
    assert registry.display_name_for(KRAKEN_ACCOUNT_ID) == KRAKEN_ACCOUNT_NAME
    assert (
        registry.resolve_owned_id(
            location=EventLocation.COINBASE,
            address=WalletAddress(COINBASE_ACCOUNT_NAME),
        )
        is None
    )
    assert registry.resolve_owned_id(location=EventLocation.BASE, address=address) == account_chain_id_for(
        location=EventLocation.BASE,
        address=address,
    )


def test_account_config_account_chain_id_for_raises_when_location_is_not_configured() -> None:
    account = AccountConfig(
        name="Primary",
        address=ETH_ADDRESS,
        locations=frozenset({EventLocation.BASE}),
        skip_sync=False,
    )

    with pytest.raises(ValueError, match="does not support location ETHEREUM"):
        account.account_chain_id_for(EventLocation.ETHEREUM)


def test_registry_rejects_configured_name_that_conflicts_with_system_account() -> None:
    with pytest.raises(ValueError, match="reserved system account name"):
        AccountRegistry(
            [
                AccountConfig(
                    name=COINBASE_ACCOUNT_NAME,
                    address=ETH_ADDRESS,
                    locations=frozenset({EventLocation.BASE}),
                    skip_sync=False,
                )
            ]
        )


def test_registry_rejects_duplicate_merged_account_chain_id() -> None:
    address = WalletAddress("0x4838b106fce9647bdf1e7877bf73ce8b0bad5f97")
    wallet_account = AccountConfig(
        name="Primary",
        address=address,
        locations=frozenset({EventLocation.BASE}),
        skip_sync=False,
    )
    duplicate_account_chain_id = account_chain_id_for(
        location=EventLocation.BASE,
        address=address,
    )

    with pytest.raises(ValueError, match="Duplicate account_chain_id"):
        AccountRegistry(
            [wallet_account],
            system_accounts=[
                AccountRecord(
                    account_chain_id=duplicate_account_chain_id,
                    display_name="Duplicate",
                )
            ],
        )


def test_registry_uses_location_suffix_for_multi_location_display_names() -> None:
    address = WalletAddress("0x4838b106fce9647bdf1e7877bf73ce8b0bad5f97")
    account = AccountConfig(
        name="Farming",
        address=address,
        locations=frozenset(
            {
                EventLocation.ETHEREUM,
                EventLocation.ARBITRUM,
                EventLocation.OPTIMISM,
                EventLocation.BASE,
            }
        ),
        skip_sync=False,
    )

    registry = AccountRegistry([account], system_accounts=())

    assert [record.display_name for record in registry.records()] == [
        "Farming:arb",
        "Farming:bas",
        "Farming:eth",
        "Farming:opt",
    ]
