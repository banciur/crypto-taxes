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

    addresses_seen: set[WalletAddress] = set()
    accounts: list[TrackedAccount] = []
    for entry in payload:
        if not isinstance(entry, dict):
            raise ValueError("Each account entry must be an object.")
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
            raise ValueError(
                "Each account entry must include 'name' (string), 'address' (string), 'chains' (list), and 'skip_sync' (bool)."
            )
        address = _normalize_address(address)
        if address in addresses_seen:
            raise ValueError(f"Duplicate address {address} in accounts file.")
        addresses_seen.add(address)
        accounts.append(
            TrackedAccount(
                name=name,
                address=address,
                chains=_normalize_chains(chains_raw),
                skip_sync=skip_sync,
            )
        )

    return accounts


__all__ = ["DEFAULT_ACCOUNTS_PATH", "TrackedAccount", "load_accounts"]
