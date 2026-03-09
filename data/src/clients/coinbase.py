from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, cast

from coinbase.rest import RESTClient

_ACCOUNT_PAGE_SIZE = 250


@dataclass(frozen=True, slots=True)
class CoinbaseBalance:
    account_uuid: str
    account_name: str
    currency: str
    value: Decimal


class CoinbaseClient:
    def __init__(self, api_key: str, api_secret: str) -> None:
        self.rest_client = RESTClient(
            api_key=api_key,
            api_secret=api_secret,
        )

    def fetch_balances(self, *, include_zero_balances: bool = False) -> list[CoinbaseBalance]:
        cursor: str | None = None
        balances: list[CoinbaseBalance] = []

        while True:
            response = self.rest_client.get_accounts(limit=_ACCOUNT_PAGE_SIZE, cursor=cursor)
            payload = response.to_dict()
            balances.extend(
                self._parse_balances(payload=payload, include_zero_balances=include_zero_balances),
            )

            if not payload.get("has_next"):
                break
            cursor = cast(str, payload["cursor"])

        return sorted(
            balances,
            key=lambda balance: (balance.currency, balance.account_name, balance.account_uuid),
        )

    def _parse_balances(
        self,
        *,
        payload: dict[str, Any],
        include_zero_balances: bool,
    ) -> list[CoinbaseBalance]:
        balances: list[CoinbaseBalance] = []
        for account in cast(list[dict[str, Any]], payload.get("accounts", [])):
            available_balance = cast(dict[str, str], account["available_balance"])
            value = Decimal(available_balance["value"])

            if not include_zero_balances and value == 0:
                continue

            balances.append(
                CoinbaseBalance(
                    account_uuid=cast(str, account["uuid"]),
                    account_name=cast(str, account["name"]),
                    currency=available_balance["currency"],
                    value=value,
                )
            )

        return balances
