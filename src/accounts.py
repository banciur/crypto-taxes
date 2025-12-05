from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_ACCOUNTS_PATH = Path("data/accounts.json")


@dataclass(frozen=True)
class TrackedAccount:
    address: str
    chains: list[str]


def _normalize_chains(chains: Iterable[object]) -> list[str]:
    return [str(chain) for chain in chains]


def load_accounts(path: Path = DEFAULT_ACCOUNTS_PATH) -> list[TrackedAccount]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        msg = "Accounts file must contain a JSON list of objects."
        raise ValueError(msg)

    accounts: list[TrackedAccount] = []
    for entry in payload:
        if not isinstance(entry, dict):
            msg = "Each account entry must be an object with 'address' and 'chains'."
            raise ValueError(msg)
        address = entry.get("address")
        chains_raw = entry.get("chains")
        if not isinstance(address, str) or not isinstance(chains_raw, list):
            msg = "Each account entry must include 'address' (string) and 'chains' (list)."
            raise ValueError(msg)
        accounts.append(TrackedAccount(address=address, chains=_normalize_chains(chains_raw)))

    return accounts


__all__ = ["DEFAULT_ACCOUNTS_PATH", "TrackedAccount", "load_accounts"]
