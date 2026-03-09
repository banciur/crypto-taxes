from __future__ import annotations

from typing import Any, cast

from coinbase.rest import RESTClient

_API_RESP_LIMIT = 100
_TRACK_ACCOUNTS_ENDPOINT = "/v2/accounts"


class CoinbaseClient:
    def __init__(self, api_key: str, api_secret: str) -> None:
        self.rest_client = RESTClient(
            api_key=api_key,
            api_secret=api_secret,
        )

    def fetch_transactions(
        self,
        *,
        order: str = "desc",
    ) -> list[dict[str, Any]]:
        accounts = self._fetch_data(
            url=_TRACK_ACCOUNTS_ENDPOINT,
        )
        transactions: list[dict] = []
        for account in accounts:
            account_id = cast(str, account["id"])
            account_transactions = self._fetch_data(
                url=f"/v2/accounts/{account_id}/transactions",
                params={
                    "order": order,
                },
            )
            transactions.extend(account_transactions)

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
