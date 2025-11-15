from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import requests
from requests import Response
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from config import config

from .price_sources import PriceSource
from .price_types import PriceQuote

logger = logging.getLogger(__name__)


class CoinDeskAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, payload: Any | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


@dataclass(frozen=True)
class SpotInstrumentOHLC:
    timestamp: datetime
    market: str
    instrument: str
    mapped_instrument: str | None
    base_asset: str | None
    quote_asset: str | None
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal
    volume: Decimal | None
    quote_volume: Decimal | None


class _CoinDeskClient:
    def __init__(
        self,
        base_url: str = "https://data-api.coindesk.com",
        timeout: float = 10.0,
        session: requests.Session | None = None,
        retry_attempts: int = 10,
        retry_backoff_seconds: float = 1,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = session or requests.Session()

        retry = Retry(
            total=retry_attempts,
            backoff_factor=retry_backoff_seconds,
            status_forcelist={429},
            allowed_methods={"GET"},
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def get_spot_historical_minutes(
        self,
        *,
        market: str,
        instrument: str,
        to_ts: int,
        limit: int = 1,
        aggregate: int = 1,
        fill: bool = True,
    ) -> list[SpotInstrumentOHLC]:
        return self._get_spot_historical(
            path="/spot/v1/historical/minutes",
            market=market,
            instrument=instrument,
            to_ts=to_ts,
            limit=limit,
            aggregate=aggregate,
            fill=fill,
        )

    def get_spot_historical_hours(
        self,
        *,
        market: str,
        instrument: str,
        to_ts: int,
        limit: int = 1,
        aggregate: int = 1,
        fill: bool = True,
    ) -> list[SpotInstrumentOHLC]:
        return self._get_spot_historical(
            path="/spot/v1/historical/hours",
            market=market,
            instrument=instrument,
            to_ts=to_ts,
            limit=limit,
            aggregate=aggregate,
            fill=fill,
        )

    def _get_spot_historical(
        self,
        *,
        path: str,
        market: str,
        instrument: str,
        to_ts: int,
        limit: int,
        aggregate: int,
        fill: bool,
    ) -> list[SpotInstrumentOHLC]:
        if limit <= 0:
            raise ValueError("limit must be > 0")
        if aggregate <= 0:
            raise ValueError("aggregate must be > 0")
        if not market:
            raise ValueError("market must be provided")
        if not instrument:
            raise ValueError("instrument must be provided")

        params = {
            "market": market,
            "instrument": instrument,
            "limit": limit,
            "aggregate": aggregate,
            "fill": "true" if fill else "false",
            "response_format": "JSON",
            "to_ts": to_ts,
        }
        payload = self._request("GET", path, params=params)
        entries = payload.get("Data") or []
        return [self._parse_histo_entry(entry) for entry in entries]

    def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = self._session.request(
                method,
                url,
                params=params,
                timeout=self.timeout,
                headers={"Authorization": f"Bearer {config().coindesk_api_key}"},
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            resp = exc.response
            message, payload_err = self._extract_error(resp)
            raise CoinDeskAPIError(message, status_code=resp.status_code, payload=payload_err) from exc
        except requests.RequestException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            raise CoinDeskAPIError("CoinDesk API request failed", status_code=status_code) from exc

        try:
            payload: dict[str, Any] = response.json()
        except ValueError as exc:
            raise CoinDeskAPIError("CoinDesk API returned invalid JSON", payload=response.text) from exc

        if not isinstance(payload, dict):
            raise CoinDeskAPIError("CoinDesk API returned unexpected payload type", payload=payload)

        err = payload.get("Err")
        if isinstance(err, dict) and err.get("message"):
            raise CoinDeskAPIError(err["message"], status_code=response.status_code, payload=payload)

        return payload

    def _parse_histo_entry(self, entry: dict[str, Any]) -> SpotInstrumentOHLC:
        ts_raw = entry.get("TIMESTAMP")
        close_raw = entry.get("CLOSE")
        if ts_raw is None or close_raw is None:
            raise CoinDeskAPIError("CoinDesk histo entry missing TIMESTAMP or CLOSE field", payload=entry)

        timestamp = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc)
        close_value = self._to_decimal(close_raw)
        if close_value is None:
            raise CoinDeskAPIError("CoinDesk histo entry contains non-numeric CLOSE", payload=entry)

        return SpotInstrumentOHLC(
            timestamp=timestamp,
            market=str(entry.get("MARKET", "")),
            instrument=str(entry.get("INSTRUMENT", "")),
            mapped_instrument=entry.get("MAPPED_INSTRUMENT"),
            base_asset=entry.get("BASE"),
            quote_asset=entry.get("QUOTE"),
            open=self._to_decimal(entry.get("OPEN")),
            high=self._to_decimal(entry.get("HIGH")),
            low=self._to_decimal(entry.get("LOW")),
            close=close_value,
            volume=self._to_decimal(entry.get("VOLUME")),
            quote_volume=self._to_decimal(entry.get("QUOTE_VOLUME")),
        )

    @staticmethod
    def _to_decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(value))

    @staticmethod
    def _extract_error(response: Response) -> tuple[str, Any]:
        message = "CoinDesk API request failed"
        try:
            payload = response.json()
            err = payload.get("Err") if isinstance(payload, dict) else None
            if isinstance(err, dict) and err.get("message"):
                message = err["message"]
        except ValueError:
            payload = response.text
        return message, payload

    def get_market_instrument(self, *, market: str, instrument: str) -> dict[str, Any] | None:
        params = {"market": market, "instrument": instrument}
        payload = self._request("GET", "/spot/v1/markets/instruments", params=params)
        data = payload.get("Data")
        if not isinstance(data, dict):
            return None

        market_key = market.lower()
        market_data = None
        for key, value in data.items():
            if key.lower() == market_key:
                market_data = value
                break
        if not isinstance(market_data, dict):
            return None

        instruments = market_data.get("instruments")
        if not isinstance(instruments, dict):
            return None

        return instruments.get(instrument.upper())


class CoinDeskSource(PriceSource):
    def __init__(
        self,
        *,
        market: str = "coinbase",
        aggregate_minutes: int = 60,
        client: _CoinDeskClient | None = None,
        source_name: str = "coindesk-spot-api",
    ) -> None:
        resolved_client = client or _CoinDeskClient()

        if aggregate_minutes <= 0:
            msg = "aggregate_minutes must be greater than 0"
            raise ValueError(msg)
        if aggregate_minutes < 60 and aggregate_minutes > 30:
            msg = "CoinDesk minute candles support aggregate_minutes up to 30"
            raise ValueError(msg)
        if aggregate_minutes >= 60 and aggregate_minutes % 60 != 0:
            msg = "aggregate_minutes must be divisible by 60 when requesting hour candles"
            raise ValueError(msg)

        if not market:
            msg = "market must be provided"
            raise ValueError(msg)

        self.client = resolved_client
        self.market = market
        self.aggregate_minutes = aggregate_minutes
        self.source_name = source_name

        if aggregate_minutes < 60:
            self._bucket_mode = "minute"
            self._aggregate_units = aggregate_minutes
            self._bucket_duration = timedelta(minutes=aggregate_minutes)
        else:
            self._bucket_mode = "hour"
            self._aggregate_units = aggregate_minutes // 60
            self._bucket_duration = timedelta(minutes=aggregate_minutes)

    def fetch_snapshot(self, base_id: str, quote_id: str, timestamp: datetime) -> PriceQuote:
        instrument = f"{base_id.upper()}-{quote_id.upper()}"
        entries, override_valid_from = self._fetch_histo_entries(instrument=instrument, timestamp=timestamp)

        if not entries:
            msg = f"No price data returned for {instrument} on {self.market}"
            raise RuntimeError(msg)

        bucket = max(entries, key=lambda entry: entry.timestamp)
        valid_from = override_valid_from or bucket.timestamp
        valid_to = valid_from + self._bucket_duration

        return PriceQuote(
            timestamp=valid_from,
            base_id=base_id.upper(),
            quote_id=quote_id.upper(),
            rate=bucket.close,
            source=self.source_name,
            valid_from=valid_from,
            valid_to=valid_to,
        )

    def _fetch_histo_entries(
        self, *, instrument: str, timestamp: datetime
    ) -> tuple[list[SpotInstrumentOHLC], datetime | None]:
        unix_ts = int(timestamp.timestamp())
        try:
            return self._call_histo_api(instrument=instrument, to_ts=unix_ts), None
        except CoinDeskAPIError as exc:
            adjusted = self._maybe_adjust_to_first_trade(instrument=instrument, requested_ts=unix_ts, error=exc)
            if adjusted is None:
                raise
            adjusted_ts, override_dt = adjusted
            return self._call_histo_api(instrument=instrument, to_ts=adjusted_ts), override_dt

    def _call_histo_api(self, *, instrument: str, to_ts: int) -> list[SpotInstrumentOHLC]:
        if self._bucket_mode == "minute":
            return self.client.get_spot_historical_minutes(
                market=self.market,
                instrument=instrument,
                to_ts=to_ts,
                limit=1,
                aggregate=self._aggregate_units,
            )

        return self.client.get_spot_historical_hours(
            market=self.market,
            instrument=instrument,
            to_ts=to_ts,
            limit=1,
            aggregate=self._aggregate_units,
        )

    def _maybe_adjust_to_first_trade(
        self,
        *,
        instrument: str,
        requested_ts: int,
        error: CoinDeskAPIError,
    ) -> tuple[int, datetime] | None:
        message = str(error)
        if error.status_code != 404 or "FIRST_TRADE_SPOT_TIMESTAMP" not in message:
            return None

        metadata = self.client.get_market_instrument(market=self.market, instrument=instrument)
        if not metadata:
            return None
        first_trade_ts = metadata.get("FIRST_TRADE_SPOT_TIMESTAMP")
        if not isinstance(first_trade_ts, int):
            return None
        if first_trade_ts <= requested_ts:
            return None

        first_dt = datetime.fromtimestamp(first_trade_ts, tz=timezone.utc)
        requested_dt = datetime.fromtimestamp(requested_ts, tz=timezone.utc)
        logger.warning(
            "CoinDesk instrument %s/%s unavailable at %s, retrying from first trade timestamp %s",
            self.market,
            instrument,
            requested_dt.isoformat(),
            first_dt.isoformat(),
        )
        return first_trade_ts, requested_dt


__all__ = ["CoinDeskSource"]
