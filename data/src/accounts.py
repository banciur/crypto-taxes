from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from pydantic import ConfigDict, field_validator

from config import ACCOUNTS_PATH
from domain.ledger import AccountChainId, EventLocation, WalletAddress
from pydantic_base import StrictBaseModel


class AccountBase(StrictBaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: str
    address: WalletAddress
    skip_sync: bool = False

    @field_validator("address", mode="before")
    @classmethod
    def _normalize_address_value(cls, value: object) -> WalletAddress:
        if not isinstance(value, str):
            raise TypeError("address must be a string")
        return _normalize_address(value)


class AccountConfig(AccountBase):
    locations: frozenset[EventLocation]

    def account_chain_id_for(self, location: EventLocation) -> AccountChainId:
        return account_chain_id_for(location=location, address=self.address)


class AccountChainRecord(AccountBase):
    account_chain_id: AccountChainId
    location: EventLocation


def _normalize_address(address: str) -> WalletAddress:
    return WalletAddress(address.strip().lower())


def account_chain_id_for(*, location: EventLocation, address: WalletAddress) -> AccountChainId:
    return AccountChainId(f"{location}:{address}")


def location_address_from_account_chain_id(account_chain_id: AccountChainId) -> tuple[EventLocation, WalletAddress]:
    location, address = account_chain_id.split(":", maxsplit=1)
    return EventLocation(location), WalletAddress(address)


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
    def __init__(self, accounts: Iterable[AccountConfig]):
        ordered_accounts = tuple(accounts)
        by_account_chain_id: dict[AccountChainId, AccountChainRecord] = {}
        for account in ordered_accounts:
            for location in account.locations:
                account_chain_id = account.account_chain_id_for(location)
                by_account_chain_id[account_chain_id] = AccountChainRecord(
                    account_chain_id=account_chain_id,
                    name=account.name,
                    location=location,
                    address=account.address,
                    skip_sync=account.skip_sync,
                )
        self._by_account_chain_id = by_account_chain_id

    @classmethod
    def from_path(cls, path: Path = ACCOUNTS_PATH) -> AccountRegistry:
        return cls(load_accounts(path))

    def resolve_owned_id(self, *, location: EventLocation, address: WalletAddress) -> AccountChainId | None:
        account_chain_id = account_chain_id_for(location=location, address=address)
        if account_chain_id not in self._by_account_chain_id:
            return None
        return account_chain_id

    def is_owned(self, account_chain_id: AccountChainId) -> bool:
        return account_chain_id in self._by_account_chain_id

    def location_address_for(self, account_chain_id: AccountChainId) -> tuple[EventLocation, WalletAddress] | None:
        record = self._by_account_chain_id.get(account_chain_id)
        if record is None:
            return None
        return record.location, record.address

    def name_for(self, account_chain_id: AccountChainId) -> str | None:
        record = self._by_account_chain_id.get(account_chain_id)
        if record is None:
            return None
        return record.name

    def records(self) -> list[AccountChainRecord]:
        return list(self._by_account_chain_id.values())


__all__ = [
    "AccountChainId",
    "AccountChainRecord",
    "AccountConfig",
    "AccountRegistry",
    "account_chain_id_for",
    "location_address_from_account_chain_id",
    "load_accounts",
]
