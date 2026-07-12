import json
from pathlib import Path
from typing import Annotated, Iterable, Self

from pydantic import StringConstraints

from config import ACCOUNTS_PATH
from domain.ledger import AccountChainId, EventLocation, WalletAddress
from pydantic_base import StrictBaseModel


class RealAccountConfig(StrictBaseModel):
    name: str
    address: Annotated[WalletAddress, StringConstraints(strip_whitespace=True, to_lower=True)]
    skip_sync: bool = False
    locations: frozenset[EventLocation]

    def account_chain_id_for(self, location: EventLocation) -> AccountChainId:
        if location not in self.locations:
            raise ValueError(f"Account '{self.name}' does not support location {location}.")
        return account_chain_id_for(location=location, address=self.address)


class ArtificialAccountConfig(StrictBaseModel):
    name: str
    account_id: Annotated[str, StringConstraints(min_length=1, strip_whitespace=True, to_lower=True)]

    @property
    def account_chain_id(self) -> AccountChainId:
        return account_chain_id_for(location=EventLocation.INTERNAL, address=WalletAddress(self.account_id))


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

ACCOUNTS_FILE_KEYS = frozenset({"real", "artificial"})


class AccountRegistry:
    def __init__(
        self,
        *,
        real_accounts: Iterable[RealAccountConfig],
        artificial_accounts: Iterable[ArtificialAccountConfig] = (),
        system_accounts: Iterable[AccountRecord] = DEFAULT_SYSTEM_ACCOUNTS,
    ):
        self._system_account_ids: set[AccountChainId] = set()
        self._by_account_chain_id: dict[AccountChainId, AccountRecord] = {}
        self._display_names: set[str] = set()
        self._real_accounts = tuple(real_accounts)
        self._add_system_accounts(system_accounts)
        self._add_real_accounts(self._real_accounts)
        self._add_artificial_accounts(artificial_accounts)

    def _add_system_accounts(self, system_accounts: Iterable[AccountRecord]) -> None:
        for system_account in system_accounts:
            self._add_account_record(system_account)
            self._system_account_ids.add(system_account.account_chain_id)

    def _add_real_accounts(
        self,
        real_accounts: Iterable[RealAccountConfig],
    ) -> None:
        for account in real_accounts:
            for location in sorted(account.locations, key=lambda location: location.value):
                account_chain_id = account.account_chain_id_for(location)
                self._add_account_record(
                    AccountRecord(
                        account_chain_id=account_chain_id,
                        display_name=(
                            account.name
                            if len(account.locations) == 1
                            else f"{account.name}:{location.value[:3].lower()}"
                        ),
                        skip_sync=account.skip_sync,
                    )
                )

    def _add_artificial_accounts(
        self,
        artificial_accounts: Iterable[ArtificialAccountConfig],
    ) -> None:
        for account in artificial_accounts:
            self._add_account_record(
                AccountRecord(
                    account_chain_id=account.account_chain_id,
                    display_name=account.name,
                    skip_sync=True,
                )
            )

    def _add_account_record(self, record: AccountRecord) -> None:
        if record.account_chain_id in self._by_account_chain_id:
            raise ValueError(f"Duplicate account_chain_id {record.account_chain_id} in merged account registry.")
        display_name_key = record.display_name.casefold()
        if display_name_key in self._display_names:
            raise ValueError(f"Duplicate account display name '{record.display_name}' in merged account registry.")
        self._by_account_chain_id[record.account_chain_id] = record
        self._display_names.add(display_name_key)

    @classmethod
    def from_path(
        cls,
        path: Path = ACCOUNTS_PATH,
        *,
        system_accounts: Iterable[AccountRecord] = DEFAULT_SYSTEM_ACCOUNTS,
    ) -> Self:
        real_accounts, artificial_accounts = _parse_accounts_file(path)
        return cls(
            real_accounts=real_accounts,
            artificial_accounts=artificial_accounts,
            system_accounts=system_accounts,
        )

    def resolve_owned_id(self, *, location: EventLocation, address: WalletAddress) -> AccountChainId | None:
        account_chain_id = account_chain_id_for(location=location, address=address)
        record = self._by_account_chain_id.get(account_chain_id)
        if record is None or account_chain_id in self._system_account_ids:
            return None
        return account_chain_id

    def display_name_for(self, account_chain_id: AccountChainId) -> str | None:
        record = self._by_account_chain_id.get(account_chain_id)
        if record is None:
            return None
        return record.display_name

    def real_accounts(self) -> list[RealAccountConfig]:
        return list(self._real_accounts)

    def records(self) -> list[AccountRecord]:
        return sorted(
            self._by_account_chain_id.values(),
            key=lambda record: (record.display_name.casefold(), record.account_chain_id),
        )


def _parse_accounts_file(path: Path) -> tuple[list[RealAccountConfig], list[ArtificialAccountConfig]]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("Accounts file must contain an object with real and artificial account lists.")
    keys = frozenset(payload)
    if keys != ACCOUNTS_FILE_KEYS:
        missing_keys = sorted(ACCOUNTS_FILE_KEYS - keys)
        unknown_keys = sorted(keys - ACCOUNTS_FILE_KEYS)
        problems = []
        if missing_keys:
            problems.append(f"missing keys: {', '.join(missing_keys)}")
        if unknown_keys:
            problems.append(f"unknown keys: {', '.join(unknown_keys)}")
        raise ValueError(
            f"Accounts file must contain exactly real and artificial account lists ({'; '.join(problems)})."
        )

    return _parse_real_accounts(payload), _parse_artificial_accounts(payload)


def _parse_real_accounts(payload: dict[str, object]) -> list[RealAccountConfig]:
    addresses_seen: set[WalletAddress] = set()
    real_accounts: list[RealAccountConfig] = []
    for entry in _read_account_list(payload, "real"):
        if not isinstance(entry, dict):
            raise TypeError("Each real account entry must be an object.")
        if "locations" not in entry:
            raise ValueError("Each real account entry must define locations.")
        raw_locations = entry["locations"]
        if not isinstance(raw_locations, list | set | frozenset | tuple):
            raise TypeError("locations must be a list, tuple, or set of locations")
        normalized_entry = dict(entry)
        normalized_entry["locations"] = frozenset(
            EventLocation(str(location).strip().upper()) for location in raw_locations
        )

        real_account = RealAccountConfig.model_validate(normalized_entry)
        if real_account.address in addresses_seen:
            raise ValueError(f"Duplicate address {real_account.address} in accounts file.")
        addresses_seen.add(real_account.address)
        real_accounts.append(real_account)
    return real_accounts


def _parse_artificial_accounts(payload: dict[str, object]) -> list[ArtificialAccountConfig]:
    artificial_ids_seen: set[str] = set()
    artificial_accounts: list[ArtificialAccountConfig] = []
    for entry in _read_account_list(payload, "artificial"):
        if not isinstance(entry, dict):
            raise TypeError("Each artificial account entry must be an object.")
        artificial_account = ArtificialAccountConfig.model_validate(entry)
        if artificial_account.account_id in artificial_ids_seen:
            raise ValueError(f"Duplicate artificial account_id {artificial_account.account_id} in accounts file.")
        artificial_ids_seen.add(artificial_account.account_id)
        artificial_accounts.append(artificial_account)
    return artificial_accounts


def _read_account_list(payload: dict[str, object], key: str) -> list[object]:
    raw_accounts = payload[key]
    if not isinstance(raw_accounts, list):
        raise TypeError(f"{key} accounts must be a list.")
    return raw_accounts
