from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from domain.ledger import ChainId, WalletAddress

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ACCOUNTS_PATH = REPO_ROOT / "artifacts" / "accounts.json"


@dataclass(frozen=True)
class TrackedAccount:
    name: str
    address: WalletAddress
    chains: list[ChainId]
    skip_sync: bool


def _normalize_address(address: str) -> WalletAddress:
    return WalletAddress(address.lower())


def _normalize_chains(chains: Iterable[object]) -> list[ChainId]:
    return [ChainId(str(chain)) for chain in chains]


def load_accounts(path: Path = DEFAULT_ACCOUNTS_PATH) -> list[TrackedAccount]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        msg = "Accounts file must contain a JSON list of objects."
        raise ValueError(msg)

    addresses_in_order: list[WalletAddress] = []
    account_by_address: dict[WalletAddress, TrackedAccount] = {}
    for entry in payload:
        if not isinstance(entry, dict):
            msg = "Each account entry must be an object."
            raise ValueError(msg)
        name = entry.get("name")
        address = entry.get("address")
        chains_raw = entry.get("chains")
        skip_sync = entry.get("skip_sync")
        if (
            not isinstance(name, str)
            or not isinstance(address, str)
            or not isinstance(chains_raw, list)
            or not isinstance(skip_sync, bool)
        ):
            msg = "Each account entry must include 'name' (string), 'address' (string), 'chains' (list), and 'skip_sync' (bool)."
            raise ValueError(msg)
        normalized_address = _normalize_address(address)
        normalized_chains = _normalize_chains(chains_raw)
        if normalized_address not in account_by_address:
            addresses_in_order.append(normalized_address)
            account_by_address[normalized_address] = TrackedAccount(
                name=name,
                address=normalized_address,
                chains=[],
                skip_sync=skip_sync,
            )
        existing_account = account_by_address[normalized_address]
        if existing_account.name != name or existing_account.skip_sync is not skip_sync:
            msg = f"Duplicate address {normalized_address} has conflicting account metadata."
            raise ValueError(msg)
        known_chains = existing_account.chains
        for chain in normalized_chains:
            if chain not in known_chains:
                known_chains.append(chain)

    return [account_by_address[address] for address in addresses_in_order]


__all__ = ["DEFAULT_ACCOUNTS_PATH", "TrackedAccount", "load_accounts"]
