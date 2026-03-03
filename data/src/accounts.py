from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from pydantic import ConfigDict, field_validator

from config import ACCOUNTS_PATH
from domain.ledger import AccountChainId, ChainId, WalletAddress
from pydantic_base import StrictBaseModel

CHAIN_ALIASES: dict[str, str] = {
    "ethereum": "eth",
}


class AccountBase(StrictBaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: str
    address: WalletAddress
    skip_sync: bool

    @field_validator("address", mode="before")
    @classmethod
    def _normalize_address_value(cls, value: object) -> WalletAddress:
        if not isinstance(value, str):
            raise TypeError("address must be a string")
        return _normalize_address(value)


class AccountConfig(AccountBase):
    chains: frozenset[ChainId]

    @field_validator("chains", mode="before")
    @classmethod
    def _normalize_chains(cls, value: object) -> frozenset[ChainId]:
        if not isinstance(value, list | set | frozenset | tuple):
            raise TypeError("chains must be a list, tuple, or set of chains")
        return frozenset(normalize_chain(str(chain)) for chain in value)

    def account_chain_id_for(self, chain: ChainId) -> AccountChainId:
        return account_chain_id_for(chain=chain, address=self.address)


class AccountChainRecord(AccountBase):
    account_chain_id: AccountChainId
    chain: ChainId


def normalize_chain(chain: str | ChainId) -> ChainId:
    normalized = str(chain).strip().lower()
    return ChainId(CHAIN_ALIASES.get(normalized, normalized))


def _normalize_address(address: str) -> WalletAddress:
    return WalletAddress(address.strip().lower())


def account_chain_id_for(*, chain: ChainId, address: WalletAddress) -> AccountChainId:
    return AccountChainId(f"{chain}:{address}")


def chain_address_from_account_chain_id(account_chain_id: AccountChainId) -> tuple[ChainId, WalletAddress]:
    chain, address = account_chain_id.split(":", maxsplit=1)
    return ChainId(chain), WalletAddress(address)


def load_accounts(path: Path = ACCOUNTS_PATH) -> list[AccountConfig]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        raise ValueError("Accounts file must contain a JSON list of objects.")

    addresses_seen: set[WalletAddress] = set()
    accounts: list[AccountConfig] = []
    for entry in payload:
        account = AccountConfig.model_validate(entry)
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
            for chain in account.chains:
                account_chain_id = account.account_chain_id_for(chain)
                by_account_chain_id[account_chain_id] = AccountChainRecord(
                    account_chain_id=account_chain_id,
                    name=account.name,
                    chain=chain,
                    address=account.address,
                    skip_sync=account.skip_sync,
                )
        self._by_account_chain_id = by_account_chain_id

    @classmethod
    def from_path(cls, path: Path = ACCOUNTS_PATH) -> AccountRegistry:
        return cls(load_accounts(path))

    def resolve_owned_id(self, *, chain: ChainId, address: WalletAddress) -> AccountChainId | None:
        account_chain_id = account_chain_id_for(chain=chain, address=address)
        if account_chain_id not in self._by_account_chain_id:
            return None
        return account_chain_id

    def is_owned(self, account_chain_id: AccountChainId) -> bool:
        return account_chain_id in self._by_account_chain_id

    def chain_address_for(self, account_chain_id: AccountChainId) -> tuple[ChainId, WalletAddress] | None:
        record = self._by_account_chain_id.get(account_chain_id)
        if record is None:
            return None
        return record.chain, record.address

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
    "CHAIN_ALIASES",
    "account_chain_id_for",
    "chain_address_from_account_chain_id",
    "load_accounts",
    "normalize_chain",
]
