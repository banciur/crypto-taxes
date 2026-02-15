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
    address: WalletAddress
    chains: list[ChainId]


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
    chains_by_address: dict[WalletAddress, list[ChainId]] = {}
    for entry in payload:
        if not isinstance(entry, dict):
            msg = "Each account entry must be an object."
            raise ValueError(msg)
        address = entry.get("address")
        chains_raw = entry.get("chains")
        if not isinstance(address, str) or not isinstance(chains_raw, list):
            msg = "Each account entry must include 'address' (string) and 'chains' (list)."
            raise ValueError(msg)
        normalized_address = _normalize_address(address)
        normalized_chains = _normalize_chains(chains_raw)
        if normalized_address not in chains_by_address:
            addresses_in_order.append(normalized_address)
            chains_by_address[normalized_address] = []
        known_chains = chains_by_address[normalized_address]
        for chain in normalized_chains:
            if chain not in known_chains:
                known_chains.append(chain)

    return [TrackedAccount(address=address, chains=chains_by_address[address]) for address in addresses_in_order]


__all__ = ["DEFAULT_ACCOUNTS_PATH", "TrackedAccount", "load_accounts"]
