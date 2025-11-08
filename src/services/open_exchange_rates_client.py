from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import requests

# API docs: https://docs.openexchangerates.org/reference/api-introduction
# API keys: https://openexchangerates.org/account/app-ids
class OpenExchangeRatesAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, payload: Any | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


@dataclass(frozen=True)
class HistoricalRates:
    date: date
    timestamp: datetime
    base: str
    rates: dict[str, Decimal]


class OpenExchangeRatesClient:
    def __init__(
        self,
        *,
        app_id: str,
        base_url: str = "https://openexchangerates.org/api",
        timeout: float = 10.0,
        session: requests.Session | None = None,
    ) -> None:
        if not app_id:
            msg = "app_id must be provided"
            raise ValueError(msg)

        self.app_id = app_id
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = session or requests.Session()

    def get_historical_rates(self, *, target_date: date) -> HistoricalRates:
        path = f"/historical/{target_date.isoformat()}.json"
        payload = self._request("GET", path)

        timestamp_raw = payload.get("timestamp")
        base_currency = payload.get("base")
        rates_raw = payload.get("rates")
        if timestamp_raw is None or base_currency is None or not isinstance(rates_raw, dict):
            raise OpenExchangeRatesAPIError("Open Exchange Rates payload missing required fields", payload=payload)

        timestamp = datetime.fromtimestamp(int(timestamp_raw), tz=timezone.utc)
        parsed_rates: dict[str, Decimal] = {}
        for code_raw, rate in rates_raw.items():
            parsed_rates[code_raw.upper()] = self._to_decimal(rate)

        return HistoricalRates(
            date=target_date,
            timestamp=timestamp,
            base=str(base_currency).upper(),
            rates=parsed_rates,
        )

    def _request(self, method: str, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        params = {"app_id": self.app_id}
        try:
            response = self._session.request(method, url, params=params, timeout=self.timeout)
            response.raise_for_status()
        except requests.HTTPError as exc:
            resp = exc.response
            status_code = getattr(resp, "status_code", None)
            payload: Any | None = None
            if resp is not None:
                try:
                    payload = resp.json()
                except ValueError:
                    payload = resp.text
            raise OpenExchangeRatesAPIError(
                "Open Exchange Rates request failed", status_code=status_code, payload=payload
            ) from exc
        except requests.RequestException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            raise OpenExchangeRatesAPIError("Open Exchange Rates request failed", status_code=status_code) from exc

        try:
            payload_raw = response.json()
        except ValueError as exc:
            raise OpenExchangeRatesAPIError("Open Exchange Rates returned invalid JSON", payload=response.text) from exc

        if not isinstance(payload_raw, dict):
            raise OpenExchangeRatesAPIError("Open Exchange Rates returned unexpected payload type", payload=payload_raw)

        if payload_raw.get("error"):
            raise OpenExchangeRatesAPIError(
                payload_raw.get("description", "Open Exchange Rates error"), payload=payload_raw
            )

        return payload_raw

    @staticmethod
    def _to_decimal(value: Any) -> Decimal:
        return Decimal(str(value))


__all__ = ["HistoricalRates", "OpenExchangeRatesAPIError", "OpenExchangeRatesClient"]
