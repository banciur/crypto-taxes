from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import requests


class CoinDeskAPIError(RuntimeError):
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


class CoinDeskClient:
    """Minimal CoinDesk Data API client covering the endpoints needed by the app."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://data-api.coindesk.com",
        timeout: float = 10.0,
        session: requests.Session | None = None,
    ) -> None:
        if not api_key:
            msg = "api_key must be provided"
            raise ValueError(msg)

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = session or requests.Session()

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
            msg = "limit must be > 0"
            raise ValueError(msg)
        if aggregate <= 0:
            msg = "aggregate must be > 0"
            raise ValueError(msg)
        if not market:
            msg = "market must be provided"
            raise ValueError(msg)
        if not instrument:
            msg = "instrument must be provided"
            raise ValueError(msg)

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
        parsed: list[SpotInstrumentOHLC] = []
        for entry in entries:
            parsed.append(self._parse_histo_entry(entry))
        return parsed

    def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = self._session.request(
                method,
                url,
                params=params,
                timeout=self.timeout,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            resp = exc.response
            status_code = getattr(resp, "status_code", None)
            error_payload: Any | None = None
            message = "CoinDesk API request failed"
            if resp is not None:
                try:
                    error_payload = resp.json()
                    err = error_payload.get("Err") if isinstance(error_payload, dict) else None
                    if isinstance(err, dict) and err.get("message"):
                        message = err["message"]
                except ValueError:
                    error_payload = resp.text
            raise CoinDeskAPIError(message, status_code=status_code, payload=error_payload) from exc
        except requests.RequestException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            raise CoinDeskAPIError("CoinDesk API request failed", status_code=status_code) from exc

        try:
            payload_raw = response.json()
        except ValueError as exc:
            raise CoinDeskAPIError("CoinDesk API returned invalid JSON", payload=response.text) from exc

        if not isinstance(payload_raw, dict):
            raise CoinDeskAPIError("CoinDesk API returned unexpected payload type", payload=payload_raw)

        payload: dict[str, Any] = payload_raw
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


__all__ = ["CoinDeskAPIError", "CoinDeskClient", "SpotInstrumentOHLC"]
