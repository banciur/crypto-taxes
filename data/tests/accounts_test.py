import json
from pathlib import Path

import pytest

from accounts import (
    COINBASE_ACCOUNT_ID,
    COINBASE_ACCOUNT_NAME,
    KRAKEN_ACCOUNT_ID,
    KRAKEN_ACCOUNT_NAME,
    AccountRecord,
    AccountRegistry,
    ArtificialAccountConfig,
    RealAccountConfig,
    account_chain_id_for,
    location_address_from_account_chain_id,
)
from domain.ledger import EventLocation, WalletAddress
from tests.constants import ETH_ADDRESS, LOCATION


def _accounts_payload(*, real: list[dict[str, object]], artificial: list[dict[str, object]] | None = None) -> str:
    return json.dumps({"real": real, "artificial": artificial or []})


def test_registry_from_path_normalizes_real_address_and_location_types(tmp_path: Path) -> None:
    name = "Main Wallet"
    skip_sync = False
    accounts_path = tmp_path / "accounts.json"
    accounts_path.write_text(
        _accounts_payload(
            real=[
                {
                    "name": name,
                    "address": ETH_ADDRESS.upper(),
                    "locations": [LOCATION.value.lower()],
                    "skip_sync": skip_sync,
                }
            ]
        )
    )

    real_accounts = AccountRegistry.from_path(accounts_path).real_accounts()

    assert len(real_accounts) == 1
    loaded_account = real_accounts[0]
    assert loaded_account.name == name
    assert loaded_account.address == ETH_ADDRESS
    assert loaded_account.locations == {LOCATION}
    assert loaded_account.skip_sync is skip_sync


def test_real_account_config_requires_preparsed_locations() -> None:
    with pytest.raises(Exception):
        RealAccountConfig.model_validate(
            {
                "name": "Wallet",
                "address": WalletAddress("0xabc"),
                "locations": ["ethereum"],
                "skip_sync": False,
            }
        )


def test_registry_from_path_raises_for_duplicate_real_address(tmp_path: Path) -> None:
    accounts_path = tmp_path / "accounts.json"
    accounts_path.write_text(
        _accounts_payload(
            real=[
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
        AccountRegistry.from_path(accounts_path)


def test_registry_from_path_defaults_real_skip_sync_to_false_when_omitted(tmp_path: Path) -> None:
    accounts_path = tmp_path / "accounts.json"
    accounts_path.write_text(
        _accounts_payload(
            real=[
                {
                    "name": "Primary",
                    "address": ETH_ADDRESS.upper(),
                    "locations": [LOCATION.value.lower()],
                }
            ]
        )
    )

    real_accounts = AccountRegistry.from_path(accounts_path).real_accounts()

    assert len(real_accounts) == 1
    assert real_accounts[0].skip_sync is False


def test_registry_resolves_owned_account_chain_ids(tmp_path: Path) -> None:
    accounts_path = tmp_path / "accounts.json"
    accounts_path.write_text(
        _accounts_payload(
            real=[
                {
                    "name": "Primary",
                    "address": ETH_ADDRESS.upper(),
                    "locations": [LOCATION.value.lower()],
                    "skip_sync": False,
                }
            ]
        )
    )

    registry = AccountRegistry.from_path(accounts_path)
    resolved = registry.resolve_owned_id(
        location=LOCATION,
        address=ETH_ADDRESS,
    )

    assert resolved is not None
    assert str(resolved) == f"{LOCATION}:{ETH_ADDRESS}"
    assert registry.display_name_for(resolved) == "Primary"
    assert location_address_from_account_chain_id(resolved) == (
        LOCATION,
        ETH_ADDRESS,
    )


def test_registry_from_path_includes_artificial_accounts(tmp_path: Path) -> None:
    name = "Polygon Artificial"
    account_id = "polygon-2021"
    account_chain_id = account_chain_id_for(
        location=EventLocation.INTERNAL,
        address=WalletAddress(account_id),
    )
    accounts_path = tmp_path / "accounts.json"
    accounts_path.write_text(
        _accounts_payload(
            real=[],
            artificial=[
                {
                    "name": name,
                    "account_id": account_id,
                }
            ],
        )
    )

    registry = AccountRegistry.from_path(accounts_path)
    artificial_record = next(record for record in registry.records() if record.account_chain_id == account_chain_id)

    assert registry.display_name_for(account_chain_id) == name
    assert artificial_record.skip_sync is True


def test_registry_from_path_raises_for_duplicate_artificial_account_id(tmp_path: Path) -> None:
    account_id = "polygon-2021"
    accounts_path = tmp_path / "accounts.json"
    accounts_path.write_text(
        _accounts_payload(
            real=[],
            artificial=[
                {
                    "name": "Polygon One",
                    "account_id": account_id.upper(),
                },
                {
                    "name": "Polygon Two",
                    "account_id": account_id,
                },
            ],
        )
    )

    with pytest.raises(ValueError, match="Duplicate artificial account_id"):
        AccountRegistry.from_path(accounts_path)


def test_registry_from_path_rejects_missing_account_file_keys(tmp_path: Path) -> None:
    accounts_path = tmp_path / "accounts.json"
    accounts_path.write_text(json.dumps({"real": []}))

    with pytest.raises(ValueError, match="missing keys: artificial"):
        AccountRegistry.from_path(accounts_path)


def test_registry_from_path_rejects_unknown_account_file_keys(tmp_path: Path) -> None:
    accounts_path = tmp_path / "accounts.json"
    accounts_path.write_text(json.dumps({"real": [], "artifical": []}))

    with pytest.raises(ValueError, match="unknown keys: artifical"):
        AccountRegistry.from_path(accounts_path)


def test_registry_includes_default_system_accounts() -> None:
    address = WalletAddress("0x4838b106fce9647bdf1e7877bf73ce8b0bad5f97")
    wallet_account = RealAccountConfig(
        name="Primary",
        address=address,
        locations=frozenset({EventLocation.BASE}),
        skip_sync=False,
    )

    registry = AccountRegistry(real_accounts=[wallet_account])

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


def test_real_account_config_account_chain_id_for_raises_when_location_is_not_configured() -> None:
    account = RealAccountConfig(
        name="Primary",
        address=ETH_ADDRESS,
        locations=frozenset({EventLocation.BASE}),
        skip_sync=False,
    )

    with pytest.raises(ValueError, match="does not support location ETHEREUM"):
        account.account_chain_id_for(EventLocation.ETHEREUM)


def test_registry_rejects_real_display_name_that_conflicts_with_system_account() -> None:
    with pytest.raises(ValueError, match="Duplicate account display name"):
        AccountRegistry(
            real_accounts=[
                RealAccountConfig(
                    name=COINBASE_ACCOUNT_NAME,
                    address=ETH_ADDRESS,
                    locations=frozenset({EventLocation.BASE}),
                    skip_sync=False,
                )
            ]
        )


def test_registry_rejects_artificial_display_name_that_conflicts_with_system_account() -> None:
    with pytest.raises(ValueError, match="Duplicate account display name"):
        AccountRegistry(
            real_accounts=[],
            artificial_accounts=[
                ArtificialAccountConfig(
                    name=COINBASE_ACCOUNT_NAME,
                    account_id="coinbase-like",
                )
            ],
        )


def test_registry_rejects_duplicate_display_names_across_account_types() -> None:
    name = "Manual"

    with pytest.raises(ValueError, match="Duplicate account display name"):
        AccountRegistry(
            real_accounts=[
                RealAccountConfig(
                    name=name,
                    address=ETH_ADDRESS,
                    locations=frozenset({EventLocation.BASE}),
                    skip_sync=False,
                )
            ],
            artificial_accounts=[
                ArtificialAccountConfig(
                    name=name,
                    account_id="manual",
                )
            ],
        )


def test_registry_rejects_duplicate_merged_account_chain_id() -> None:
    address = WalletAddress("0x4838b106fce9647bdf1e7877bf73ce8b0bad5f97")
    wallet_account = RealAccountConfig(
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
            real_accounts=[wallet_account],
            system_accounts=[
                AccountRecord(
                    account_chain_id=duplicate_account_chain_id,
                    display_name="Duplicate",
                )
            ],
        )


def test_registry_uses_location_suffix_for_multi_location_display_names() -> None:
    address = WalletAddress("0x4838b106fce9647bdf1e7877bf73ce8b0bad5f97")
    account = RealAccountConfig(
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

    registry = AccountRegistry(real_accounts=[account], system_accounts=())

    assert [record.display_name for record in registry.records()] == [
        "Farming:arb",
        "Farming:bas",
        "Farming:eth",
        "Farming:opt",
    ]
