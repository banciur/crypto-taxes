from __future__ import annotations

import hashlib
import random
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Iterable, Protocol

from config import config

from .coindesk_client import CoinDeskClient, SpotInstrumentOHLC
from .open_exchange_rates_client import HistoricalRates, OpenExchangeRatesClient
from .price_types import PriceQuote


class PriceSource(Protocol):
    def fetch_snapshot(self, base_id: str, quote_id: str, timestamp: datetime) -> PriceQuote: ...


class DeterministicRandomPriceSource(PriceSource):
    def __init__(
        self,
        *,
        seed: int = 0,
        min_price: Decimal = Decimal("10"),
        max_price: Decimal = Decimal("70000"),
        source_name: str = "deterministic-rng",
    ) -> None:
        if min_price <= 0:
            msg = "min_price must be > 0"
            raise ValueError(msg)
        if max_price <= min_price:
            msg = "max_price must be greater than min_price"
            raise ValueError(msg)

        self.seed = seed
        self.min_price = min_price
        self.max_price = max_price
        self.source_name = source_name

    def fetch_snapshot(self, base_id: str, quote_id: str, timestamp: datetime) -> PriceQuote:
        rate = self._generate_rate(base_id=base_id, quote_id=quote_id, timestamp=timestamp)
        return PriceQuote(
            timestamp=timestamp,
            base_id=base_id,
            quote_id=quote_id,
            rate=rate,
            source=self.source_name,
            valid_from=timestamp,
            valid_to=timestamp,
        )

    def _generate_rate(self, *, base_id: str, quote_id: str, timestamp: datetime) -> Decimal:
        digest_input = "|".join([base_id.upper(), quote_id.upper(), timestamp.isoformat(timespec="seconds")])
        digest = hashlib.sha256(digest_input.encode("utf-8")).digest()
        seed = self.seed ^ int.from_bytes(digest, "big", signed=False)
        rng = random.Random(seed)
        scale = Decimal("0.01")
        min_scaled = self._scale_to_int(self.min_price, scale)
        max_scaled = self._scale_to_int(self.max_price, scale)
        selected = rng.randint(min_scaled, max_scaled)
        return (Decimal(selected) * scale).quantize(scale)

    @staticmethod
    def _scale_to_int(value: Decimal, scale: Decimal) -> int:
        scale_factor = int((Decimal(1) / scale).to_integral_value())
        return int((value * scale_factor).to_integral_value())


class CoinDeskPriceSource(PriceSource):
    def __init__(
        self,
        *,
        market: str = "coinbase",
        aggregate_minutes: int = 60,
        client: CoinDeskClient | None = None,
        source_name: str = "coindesk-spot-api",
    ) -> None:
        resolved_client = client
        if resolved_client is None:
            resolved_client = CoinDeskClient()

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
        instrument = self._format_instrument(base_id, quote_id)
        entries = self._fetch_histo_entries(instrument=instrument, timestamp=timestamp)

        if not entries:
            msg = f"No price data returned for {instrument} on {self.market}"
            raise RuntimeError(msg)

        bucket = max(entries, key=lambda entry: entry.timestamp)
        valid_from = bucket.timestamp
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

    def _fetch_histo_entries(self, *, instrument: str, timestamp: datetime) -> list[SpotInstrumentOHLC]:
        unix_ts = int(timestamp.timestamp())
        if self._bucket_mode == "minute":
            return self.client.get_spot_historical_minutes(
                market=self.market,
                instrument=instrument,
                to_ts=unix_ts,
                limit=1,
                aggregate=self._aggregate_units,
            )

        return self.client.get_spot_historical_hours(
            market=self.market,
            instrument=instrument,
            to_ts=unix_ts,
            limit=1,
            aggregate=self._aggregate_units,
        )

    @staticmethod
    def _format_instrument(base_id: str, quote_id: str) -> str:
        base = base_id.upper()
        quote = quote_id.upper()
        return f"{base}-{quote}"


class OpenExchangeRatesPriceSource(PriceSource):
    def __init__(
        self,
        *,
        app_id: str | None = None,
        client: OpenExchangeRatesClient | None = None,
        source_name: str = "open-exchange-rates-historical",
    ) -> None:
        resolved_client = client
        if resolved_client is None:
            resolved_app_id = app_id or config().open_exchange_rates_app_id
            if not resolved_app_id:
                msg = "Open Exchange Rates app_id must be provided"
                raise ValueError(msg)
            resolved_client = OpenExchangeRatesClient(app_id=resolved_app_id)

        self.client = resolved_client
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


class HybridPriceSource(PriceSource):
    def __init__(
        self,
        *,
        crypto_source: PriceSource,
        fiat_source: PriceSource,
        fiat_currency_codes: Iterable[str] | None = None,
    ) -> None:
        self.crypto_source = crypto_source
        self.fiat_source = fiat_source
        fiat_codes = {code.upper() for code in (fiat_currency_codes or ("EUR", "PLN", "USD"))}
        if not fiat_codes:
            msg = "fiat_currency_codes must contain at least one entry"
            raise ValueError(msg)
        self._fiat_codes = frozenset(fiat_codes)

    def fetch_snapshot(self, base_id: str, quote_id: str, timestamp: datetime) -> PriceQuote:
        base = base_id.upper()
        quote = quote_id.upper()
        if self._is_fiat_pair(base, quote):
            return self.fiat_source.fetch_snapshot(base, quote, timestamp)
        return self.crypto_source.fetch_snapshot(base, quote, timestamp)

    def _is_fiat_pair(self, base: str, quote: str) -> bool:
        return base in self._fiat_codes and quote in self._fiat_codes


__all__ = [
    "CoinDeskPriceSource",
    "DeterministicRandomPriceSource",
    "HybridPriceSource",
    "OpenExchangeRatesPriceSource",
    "PriceSource",
]
