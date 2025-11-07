from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Protocol

from config import config

from .coindesk_client import CoinDeskClient, SpotInstrumentOHLC
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
        api_key: str | None = None,
        market: str = "coinbase",
        aggregate_minutes: int = 60,
        client: CoinDeskClient | None = None,
        source_name: str = "coindesk-spot-api",
    ) -> None:
        resolved_client = client
        if resolved_client is None:
            resolved_api_key = api_key or config().coindesk_api_key
            resolved_client = CoinDeskClient(api_key=resolved_api_key)

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
        ts_utc = self._ensure_utc(timestamp)
        instrument = self._format_instrument(base_id, quote_id)
        entries = self._fetch_histo_entries(instrument=instrument, timestamp=ts_utc)

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
    def _ensure_utc(ts: datetime) -> datetime:
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)

    @staticmethod
    def _format_instrument(base_id: str, quote_id: str) -> str:
        base = base_id.upper()
        quote = quote_id.upper()
        return f"{base}-{quote}"


__all__ = ["CoinDeskPriceSource", "DeterministicRandomPriceSource", "PriceSource"]
