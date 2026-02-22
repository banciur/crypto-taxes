from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from domain.ledger import AccountChainId, ChainId, WalletAddress

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ACCOUNTS_PATH = REPO_ROOT / "artifacts" / "accounts.json"
CHAIN_ALIASES: dict[str, str] = {
    "ethereum": "eth",
}


@dataclass(frozen=True)
class AccountConfig:
    name: str
    address: WalletAddress
    chains: frozenset[ChainId]
    skip_sync: bool

    def account_chain_id_for(self, chain: ChainId) -> AccountChainId:
        return account_chain_id_for(chain=chain, address=self.address)


@dataclass(frozen=True)
class AccountChainRecord:
    account_chain_id: AccountChainId
    name: str
    chain: ChainId
    address: WalletAddress
    skip_sync: bool


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


def load_accounts(path: Path = DEFAULT_ACCOUNTS_PATH) -> list[AccountConfig]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        raise ValueError("Accounts file must contain a JSON list of objects.")

    addresses_seen: set[WalletAddress] = set()
    accounts: list[AccountConfig] = []
    for entry in payload:
        if not isinstance(entry, dict):
            raise ValueError("Each account entry must be an object.")
        name = entry.get("name")
        address_raw = entry.get("address")
        chains_raw = entry.get("chains")
        skip_sync = entry.get("skip_sync")
        if (
            not isinstance(name, str)
            or not isinstance(address_raw, str)
            or not isinstance(chains_raw, list)
            or not isinstance(skip_sync, bool)
        ):
            raise ValueError(
                "Each account entry must include 'name' (string), 'address' (string), 'chains' (list), and 'skip_sync' (bool)."
            )
        address = _normalize_address(address_raw)
        if address in addresses_seen:
            raise ValueError(f"Duplicate address {address} in accounts file.")
        addresses_seen.add(address)

        accounts.append(
            AccountConfig(
                name=name,
                address=address,
                chains=frozenset(normalize_chain(str(chain)) for chain in chains_raw),
                skip_sync=skip_sync,
            )
        )

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
    def from_path(cls, path: Path = DEFAULT_ACCOUNTS_PATH) -> AccountRegistry:
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
    "DEFAULT_ACCOUNTS_PATH",
    "account_chain_id_for",
    "chain_address_from_account_chain_id",
    "load_accounts",
    "normalize_chain",
]
