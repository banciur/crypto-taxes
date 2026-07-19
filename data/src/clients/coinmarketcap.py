# This file is completely vibed and I didn't read it.
# CoinMarketCap docs for humans: https://coinmarketcap.com/api/documentation/
# CoinMarketCap docs for LLMs: https://pro.coinmarketcap.com/llms.txt

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import requests
from requests import Response
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from config import CMC_CONFIG_PATH
from domain.ledger import AssetId
from domain.pricing import PriceRecord
from utils.misc import utc_now

from .errors import PriceClientError

logger = logging.getLogger(__name__)

_HISTORICAL_QUOTES_PATH = "/v3/cryptocurrency/quotes/historical"
_ASSET_MAP_PATH = "/v1/cryptocurrency/map"
_FIVE_MINUTES = timedelta(minutes=5)
_ONE_DAY = timedelta(days=1)
# Candidate fields surfaced to the operator when a symbol maps to more than one CMC asset.
_CANDIDATE_FIELDS = ("id", "name", "symbol", "rank", "is_active")


class CoinMarketCapAPIError(PriceClientError):
    def __init__(self, message: str, *, status_code: int | None = None, payload: Any | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


@dataclass(frozen=True)
class _Interval:
    """The resolution used for a historical quote and the half-open window it covers."""

    name: str  # CMC ``interval`` value: "5m" or "daily"
    valid_from: datetime
    valid_to: datetime


class CoinMarketCapClient:
    """CoinMarketCap Pro API price source.

    Implements :class:`domain.pricing.PriceSource` for crypto legs. Both structures it needs come
    from an operator-editable JSON config (``artifacts/cmc_config.json``), loaded once at startup:

    - ``asset_map``: symbol -> numeric CMC id, because CMC symbols collide. The base asset is
      resolved through it before any historical quote is requested; newly discovered ids are
      written back.
    - ``unpriceable``: symbols CMC prices incorrectly (illiquid LP tokens, wrapped receipts). A
      listed symbol short-circuits to an unpriceable record (``rate=None``) without any request,
      leaving its EUR value to a ``PriceOverride`` or the adjacent/remainder solver downstream.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://pro-api.coinmarketcap.com",
        timeout: float = 10.0,
        session: requests.Session | None = None,
        retry_attempts: int = 5,
        retry_backoff_seconds: float = 1,
        high_resolution_days: int = 30,
        config_path: Path = CMC_CONFIG_PATH,
        source_name: str = "coinmarketcap",
    ) -> None:
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = session or requests.Session()
        self.high_resolution_days = high_resolution_days
        self.config_path = config_path
        self.source_name = source_name
        self._asset_map, self._unpriceable = self._load_config()

        retries = Retry(
            total=retry_attempts,
            backoff_factor=retry_backoff_seconds,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def fetch_record(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> PriceRecord:
        base = AssetId(base_id.upper())
        quote = AssetId(quote_id.upper())

        interval = self._select_interval(timestamp)
        if base in self._unpriceable:
            logger.info(
                "Symbol %s is configured unpriceable; skipping CoinMarketCap and treating it as unpriceable", base
            )
            rate = None
        else:
            try:
                cmc_id = self._resolve_cmc_id(base)
            except CoinMarketCapAPIError as exc:
                if _is_invalid_symbol_error(exc, base):
                    logger.info("CoinMarketCap rejected symbol %s as invalid; treating it as unpriceable", base)
                    rate = None
                else:
                    raise
            else:
                rate = self._fetch_price(cmc_id=cmc_id, quote=quote, interval=interval)

        return PriceRecord(
            base_id=base,
            quote_id=quote,
            rate=rate,
            source=self.source_name,
            valid_from=interval.valid_from,
            valid_to=interval.valid_to,
            fetched_at=utc_now(),
        )

    def _select_interval(self, timestamp: datetime) -> _Interval:
        """Recent timestamps use 5-minute quotes; older ones use daily quotes.

        The Startup/Standard plan only grants a rolling window of high-resolution history, so
        ``5m`` requests for old timestamps fail with an access-window error. The cutoff is
        configurable rather than probed dynamically.
        """
        moment = timestamp.astimezone(timezone.utc)
        cutoff = utc_now() - timedelta(days=self.high_resolution_days)
        if moment >= cutoff:
            valid_from = _floor_to_five_minutes(moment)
            return _Interval(name="5m", valid_from=valid_from, valid_to=valid_from + _FIVE_MINUTES)
        valid_from = _floor_to_day(moment)
        return _Interval(name="daily", valid_from=valid_from, valid_to=valid_from + _ONE_DAY)

    def _fetch_price(self, *, cmc_id: int, quote: AssetId, interval: _Interval) -> Decimal | None:
        payload = self._request(
            _HISTORICAL_QUOTES_PATH,
            params={
                "id": cmc_id,
                "convert": quote,
                "interval": interval.name,
                "time_start": int(interval.valid_from.timestamp()),
                "count": 1,
            },
        )

        data = payload.get("data")
        if not isinstance(data, dict):
            raise CoinMarketCapAPIError("CoinMarketCap historical response missing data object", payload=payload)
        if not data:
            # ``data == {}``: backend confirmed there is no quote for this asset/time.
            return None

        entry = data.get(str(cmc_id))
        if not isinstance(entry, dict):
            raise CoinMarketCapAPIError(
                f"CoinMarketCap historical response missing entry for id {cmc_id}", payload=payload
            )

        quotes = entry.get("quotes")
        if not isinstance(quotes, list):
            raise CoinMarketCapAPIError("CoinMarketCap historical entry missing quotes list", payload=payload)
        if not quotes:
            # ``quotes == []``: backend confirmed there is no quote for this time.
            return None

        return self._extract_price(quote=quote, quote_point=quotes[0], payload=payload)

    def _extract_price(self, *, quote: AssetId, quote_point: Any, payload: Any) -> Decimal:
        quote_map = quote_point.get("quote") if isinstance(quote_point, dict) else None
        if not isinstance(quote_map, dict):
            raise CoinMarketCapAPIError("CoinMarketCap quote point missing quote object", payload=payload)

        quote_entry = quote_map.get(quote)
        if not isinstance(quote_entry, dict) or "price" not in quote_entry:
            raise CoinMarketCapAPIError(f"CoinMarketCap quote point missing convert currency {quote}", payload=payload)

        price_raw = quote_entry["price"]
        try:
            return Decimal(str(price_raw))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise CoinMarketCapAPIError(
                f"CoinMarketCap returned non-numeric price {price_raw!r}", payload=payload
            ) from exc

    def _resolve_cmc_id(self, symbol: AssetId) -> int:
        if symbol in self._asset_map:
            return self._asset_map[symbol]

        cmc_id = self._discover_cmc_id(symbol)
        self._asset_map[symbol] = cmc_id
        self._write_config()
        logger.info("Mapped symbol %s to CoinMarketCap id %s in %s", symbol, cmc_id, self.config_path)
        return cmc_id

    def _discover_cmc_id(self, symbol: AssetId) -> int:
        payload = self._request(_ASSET_MAP_PATH, params={"symbol": symbol})
        candidates = payload.get("data")
        if not isinstance(candidates, list):
            raise CoinMarketCapAPIError("CoinMarketCap map response missing data list", payload=payload)

        if len(candidates) == 0:
            raise CoinMarketCapAPIError(
                f'CoinMarketCap has no asset for symbol {symbol}. Add "{symbol}": <cmc_id> under "asset_map" in '
                f'{self.config_path}, or list it under "unpriceable" to treat it as unpriceable.'
            )
        if len(candidates) > 1:
            summaries = [self._candidate_summary(candidate) for candidate in candidates]
            raise CoinMarketCapAPIError(
                f"CoinMarketCap returned {len(candidates)} candidates for symbol {symbol}. "
                f'Choose one and add "{symbol}": <cmc_id> under "asset_map" in {self.config_path}. '
                f"Candidates: {summaries}"
            )

        cmc_id = candidates[0].get("id")
        if not isinstance(cmc_id, int):
            raise CoinMarketCapAPIError("CoinMarketCap map candidate missing integer id", payload=payload)
        return cmc_id

    @staticmethod
    def _candidate_summary(candidate: dict[str, Any]) -> dict[str, Any]:
        platform = candidate.get("platform")
        platform = platform if isinstance(platform, dict) else {}
        summary: dict[str, Any] = {field: candidate.get(field) for field in _CANDIDATE_FIELDS}
        summary["platform"] = platform.get("name")
        summary["token_address"] = platform.get("token_address")
        return summary

    def _load_config(self) -> tuple[dict[AssetId, int], frozenset[AssetId]]:
        if not self.config_path.exists():
            return {}, frozenset()
        try:
            raw = json.loads(self.config_path.read_text())
        except (OSError, ValueError) as exc:
            raise CoinMarketCapAPIError(f"Failed to read CoinMarketCap config at {self.config_path}") from exc
        if not isinstance(raw, dict):
            raise CoinMarketCapAPIError(f"CoinMarketCap config at {self.config_path} must be a JSON object")
        return self._parse_asset_map(raw.get("asset_map", {})), self._parse_unpriceable(raw.get("unpriceable", []))

    def _parse_asset_map(self, raw: Any) -> dict[AssetId, int]:
        if not isinstance(raw, dict):
            raise CoinMarketCapAPIError(f'CoinMarketCap config "asset_map" at {self.config_path} must be a JSON object')
        try:
            return {AssetId(str(symbol).upper()): int(cmc_id) for symbol, cmc_id in raw.items()}
        except (TypeError, ValueError) as exc:
            raise CoinMarketCapAPIError(
                f'CoinMarketCap config "asset_map" at {self.config_path} must map symbols to integer ids'
            ) from exc

    def _parse_unpriceable(self, raw: Any) -> frozenset[AssetId]:
        if not isinstance(raw, list) or not all(isinstance(symbol, str) for symbol in raw):
            raise CoinMarketCapAPIError(
                f'CoinMarketCap config "unpriceable" at {self.config_path} must be a JSON list of symbol strings'
            )
        return frozenset(AssetId(symbol.upper()) for symbol in raw)

    def _write_config(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "asset_map": {symbol: self._asset_map[symbol] for symbol in sorted(self._asset_map)},
            "unpriceable": sorted(self._unpriceable),
        }
        self.config_path.write_text(json.dumps(payload, indent=2) + "\n")

    def _request(self, path: str, *, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {"X-CMC_PRO_API_KEY": self._api_key, "Accept": "application/json"}
        try:
            response = self._session.get(url, params=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()
        except requests.HTTPError as exc:
            resp = exc.response
            message, payload = self._extract_error(resp)
            raise CoinMarketCapAPIError(
                message, status_code=getattr(resp, "status_code", None), payload=payload
            ) from exc
        except requests.RequestException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            raise CoinMarketCapAPIError("CoinMarketCap request failed", status_code=status_code) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise CoinMarketCapAPIError("CoinMarketCap returned invalid JSON", payload=response.text) from exc

        if not isinstance(payload, dict):
            raise CoinMarketCapAPIError("CoinMarketCap returned unexpected payload type", payload=payload)

        status = payload.get("status")
        if not isinstance(status, dict):
            raise CoinMarketCapAPIError("CoinMarketCap response missing status object", payload=payload)
        error_code = status.get("error_code")
        if error_code:
            message = status.get("error_message") or "CoinMarketCap API error"
            raise CoinMarketCapAPIError(message, status_code=response.status_code, payload=payload)

        return payload

    @staticmethod
    def _extract_error(response: Response | None) -> tuple[str, Any | None]:
        message = "CoinMarketCap request failed"
        if response is None:
            return message, None
        try:
            payload = response.json()
        except ValueError:
            return message, response.text
        if isinstance(payload, dict):
            status = payload.get("status")
            if isinstance(status, dict) and status.get("error_message"):
                message = status["error_message"]
        return message, payload


def _floor_to_five_minutes(moment: datetime) -> datetime:
    return moment.replace(minute=moment.minute - moment.minute % 5, second=0, microsecond=0)


def _floor_to_day(moment: datetime) -> datetime:
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


def _is_invalid_symbol_error(error: CoinMarketCapAPIError, symbol: AssetId) -> bool:
    return str(error) == f'Invalid value for "symbol": "{symbol}"'
