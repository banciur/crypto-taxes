from __future__ import annotations

from typing import Any, cast

from coinbase.rest import RESTClient

_API_RESP_LIMIT = 100


class CoinbaseClient:
    def __init__(self, api_key: str, api_secret: str) -> None:
        self.rest_client = RESTClient(
            api_key=api_key,
            api_secret=api_secret,
        )

    def fetch_accounts(self) -> list[dict[str, Any]]:
        return self._fetch_data(url="/v2/accounts")

    def fetch_account_transactions(
        self,
        account_id: str,
        *,
        order: str = "desc",
    ) -> list[dict[str, Any]]:
        return self._fetch_data(
            url=f"/v2/accounts/{account_id}/transactions",
            params={"order": order},
        )

    def fetch_transactions(
        self,
        *,
        order: str = "desc",
        accounts: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        fetched_accounts = accounts if accounts is not None else self.fetch_accounts()
        transactions: list[dict[str, Any]] = []
        for account in fetched_accounts:
            account_id = cast(str, account["id"])
            transactions.extend(self.fetch_account_transactions(account_id, order=order))

        return sorted(
            transactions,
            key=lambda tx: cast(str, tx.get("created_at") or ""),
            reverse=order == "desc",
        )

    def _fetch_data(
        self,
        *,
        url: str,
        params: dict | None = None,
        next_starting_after: str | None = None,
    ) -> list[dict]:
        p = params or {}
        cursor = next_starting_after
        records: list[dict] = []

        while True:
            payload = self.rest_client.get(
                url,
                params={
                    **p,
                    "limit": _API_RESP_LIMIT,
                    "starting_after": cursor,
                },
            )

            records.extend(payload.get("data", []))
            cursor = self._obtain_next(payload)
            if cursor is None:
                break

        return records

    @staticmethod
    def _obtain_next(payload: dict[str, Any]) -> str | None:
        return cast(str | None, payload.get("pagination", {}).get("next_starting_after"))
