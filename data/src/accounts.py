from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Iterable

from pydantic import StringConstraints

from config import ACCOUNTS_PATH
from domain.ledger import AccountChainId, EventLocation, WalletAddress
from pydantic_base import StrictBaseModel


class AccountConfig(StrictBaseModel):
    name: str
    address: Annotated[WalletAddress, StringConstraints(strip_whitespace=True, to_lower=True)]
    skip_sync: bool = False
    locations: frozenset[EventLocation]

    def account_chain_id_for(self, location: EventLocation) -> AccountChainId:
        if location not in self.locations:
            raise ValueError(f"Account '{self.name}' does not support location {location}.")
        return account_chain_id_for(location=location, address=self.address)


class AccountRecord(StrictBaseModel):
    account_chain_id: AccountChainId
    display_name: str
    skip_sync: bool = False


def account_chain_id_for(*, location: EventLocation, address: WalletAddress) -> AccountChainId:
    return AccountChainId(f"{location}:{address}")


def location_address_from_account_chain_id(account_chain_id: AccountChainId) -> tuple[EventLocation, WalletAddress]:
    location, address = account_chain_id.split(":", maxsplit=1)
    return EventLocation(location), WalletAddress(address)


COINBASE_ACCOUNT_NAME = "coinbase"
KRAKEN_ACCOUNT_NAME = "kraken"

COINBASE_ACCOUNT_ID = account_chain_id_for(
    location=EventLocation.COINBASE,
    address=WalletAddress(COINBASE_ACCOUNT_NAME),
)
KRAKEN_ACCOUNT_ID = account_chain_id_for(
    location=EventLocation.KRAKEN,
    address=WalletAddress(KRAKEN_ACCOUNT_NAME),
)

DEFAULT_SYSTEM_ACCOUNTS: tuple[AccountRecord, ...] = (
    AccountRecord(
        account_chain_id=COINBASE_ACCOUNT_ID,
        display_name=COINBASE_ACCOUNT_NAME,
    ),
    AccountRecord(
        account_chain_id=KRAKEN_ACCOUNT_ID,
        display_name=KRAKEN_ACCOUNT_NAME,
    ),
)


def load_accounts(path: Path = ACCOUNTS_PATH) -> list[AccountConfig]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        raise ValueError("Accounts file must contain a JSON list of objects.")

    addresses_seen: set[WalletAddress] = set()
    accounts: list[AccountConfig] = []
    for entry in payload:
        if not isinstance(entry, dict):
            raise TypeError("Each account entry must be an object.")
        if "locations" not in entry:
            raise ValueError("Each account entry must define locations.")
        raw_locations = entry["locations"]
        if not isinstance(raw_locations, list | set | frozenset | tuple):
            raise TypeError("locations must be a list, tuple, or set of locations")
        normalized_entry = dict(entry)
        normalized_entry["locations"] = frozenset(
            EventLocation(str(location).strip().upper()) for location in raw_locations
        )

        account = AccountConfig.model_validate(normalized_entry)
        if account.address in addresses_seen:
            raise ValueError(f"Duplicate address {account.address} in accounts file.")
        addresses_seen.add(account.address)
        accounts.append(account)

    return accounts


class AccountRegistry:
    def __init__(
        self,
        accounts: Iterable[AccountConfig],
        *,
        system_accounts: Iterable[AccountRecord] = DEFAULT_SYSTEM_ACCOUNTS,
    ):
        reserved_system_names: set[str] = set()
        self._system_account_ids: set[AccountChainId] = set()
        self._by_account_chain_id: dict[AccountChainId, AccountRecord] = {}

        for system_account in system_accounts:
            if system_account.account_chain_id in self._by_account_chain_id:
                raise ValueError(
                    f"Duplicate account_chain_id {system_account.account_chain_id} in merged account registry."
                )
            self._by_account_chain_id[system_account.account_chain_id] = system_account
            reserved_system_names.add(system_account.display_name.casefold())
            self._system_account_ids.add(system_account.account_chain_id)

        for account in accounts:
            if account.name.casefold() in reserved_system_names:
                raise ValueError(
                    f"Configured account name '{account.name}' conflicts with reserved system account name."
                )

            for location in sorted(account.locations, key=lambda location: location.value):
                account_chain_id = account.account_chain_id_for(location)
                if account_chain_id in self._by_account_chain_id:
                    raise ValueError(f"Duplicate account_chain_id {account_chain_id} in merged account registry.")

                self._by_account_chain_id[account_chain_id] = AccountRecord(
                    account_chain_id=account_chain_id,
                    display_name=(
                        account.name if len(account.locations) == 1 else f"{account.name}:{location.value[:3].lower()}"
                    ),
                    skip_sync=account.skip_sync,
                )

    @classmethod
    def from_path(cls, path: Path = ACCOUNTS_PATH) -> AccountRegistry:
        return cls(load_accounts(path))

    def resolve_owned_id(self, *, location: EventLocation, address: WalletAddress) -> AccountChainId | None:
        account_chain_id = account_chain_id_for(location=location, address=address)
        record = self._by_account_chain_id.get(account_chain_id)
        if record is None or account_chain_id in self._system_account_ids:
            return None
        return account_chain_id

    def is_owned(self, account_chain_id: AccountChainId) -> bool:
        return account_chain_id in self._by_account_chain_id

    def display_name_for(self, account_chain_id: AccountChainId) -> str | None:
        record = self._by_account_chain_id.get(account_chain_id)
        if record is None:
            return None
        return record.display_name

    def records(self) -> list[AccountRecord]:
        return sorted(
            self._by_account_chain_id.values(),
            key=lambda record: (record.display_name.casefold(), record.account_chain_id),
        )
