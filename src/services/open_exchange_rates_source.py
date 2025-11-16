from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

import requests
from requests import Response
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from config import config

from .price_sources import PriceSnapshotSource
from .price_types import PriceQuote


class OpenExchangeRatesAPIError(Exception):
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


class _OpenExchangeRatesClient:
    def __init__(
        self,
        base_url: str = "https://openexchangerates.org/api",
        timeout: float = 10.0,
        session: requests.Session | None = None,
        retry_attempts: int = 5,
        retry_backoff_seconds: float = 1,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = session or requests.Session()

        retries = Retry(
            total=retry_attempts,
            backoff_factor=retry_backoff_seconds,
            status_forcelist=[429],
            allowed_methods=frozenset({"GET"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def get_historical_rates(self, *, target_date: date) -> HistoricalRates:
        path = f"/historical/{target_date.isoformat()}.json"
        payload = self._request("GET", path)

        timestamp_raw = payload.get("timestamp")
        base_currency = payload.get("base")
        rates_raw = payload.get("rates")
        if timestamp_raw is None or base_currency is None or not isinstance(rates_raw, dict):
            raise OpenExchangeRatesAPIError("Open Exchange Rates payload missing required fields", payload=payload)

        timestamp = datetime.fromtimestamp(int(timestamp_raw), tz=timezone.utc)
        parsed_rates: dict[str, Decimal] = {
            code_raw.upper(): self._to_decimal(rate) for code_raw, rate in rates_raw.items()
        }

        return HistoricalRates(
            date=target_date,
            timestamp=timestamp,
            base=str(base_currency).upper(),
            rates=parsed_rates,
        )

    def _request(self, method: str, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        params = {"app_id": config().open_exchange_rates_app_id}
        try:
            response = self._session.request(method, url, params=params, timeout=self.timeout)
            response.raise_for_status()
        except requests.HTTPError as exc:
            resp = exc.response
            status_code = getattr(resp, "status_code", None)
            message, payload = self._extract_error(resp)
            raise OpenExchangeRatesAPIError(message, status_code=status_code, payload=payload) from exc
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
            message = payload_raw.get("description") or payload_raw.get("message") or "Open Exchange Rates error"
            raise OpenExchangeRatesAPIError(message, payload=payload_raw)

        return payload_raw

    @staticmethod
    def _to_decimal(value: Any) -> Decimal:
        return Decimal(str(value))

    @staticmethod
    def _extract_error(response: Response | None) -> tuple[str, Any | None]:
        message = "Open Exchange Rates request failed"
        payload: Any | None = None
        if response is None:
            return message, payload

        try:
            payload = response.json()
            if isinstance(payload, dict):
                message = payload.get("description") or payload.get("message") or message
        except ValueError:
            payload = response.text
        return message, payload


class OpenExchangeRatesSource(PriceSnapshotSource):
    def __init__(
        self,
        *,
        client: _OpenExchangeRatesClient | None = None,
        source_name: str = "open-exchange-rates-historical",
    ) -> None:
        self.client = client or _OpenExchangeRatesClient()
        self.source_name = source_name

    def fetch_snapshot(self, base_id: str, quote_id: str, timestamp: datetime) -> PriceQuote:
        snapshot = self.client.get_historical_rates(target_date=timestamp.date())

        base = base_id.upper()
        quote = quote_id.upper()

        rate = self._compute_rate(snapshot=snapshot, base=base, quote=quote)
        valid_from = datetime.combine(snapshot.date, time.min, tzinfo=timezone.utc)
        valid_to = valid_from + timedelta(days=1)

        return PriceQuote(
            timestamp=snapshot.timestamp,
            base_id=base,
            quote_id=quote,
            rate=rate,
            source=self.source_name,
            valid_from=valid_from,
            valid_to=valid_to,
        )

    def _compute_rate(self, *, snapshot: HistoricalRates, base: str, quote: str) -> Decimal:
        if base == quote:
            return Decimal("1")

        base_rate = self._resolve_rate(snapshot=snapshot, currency=base)
        quote_rate = self._resolve_rate(snapshot=snapshot, currency=quote)
        return quote_rate / base_rate

    @staticmethod
    def _resolve_rate(*, snapshot: HistoricalRates, currency: str) -> Decimal:
        if currency == snapshot.base:
            return Decimal("1")
        try:
            return snapshot.rates[currency]
        except KeyError as exc:
            msg = f"Currency {currency} not available in Open Exchange Rates data"
            raise RuntimeError(msg) from exc


__all__ = ["OpenExchangeRatesSource"]
