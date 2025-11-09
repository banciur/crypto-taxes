from __future__ import annotations

import hashlib
import random
from datetime import datetime
from decimal import Decimal
from typing import Iterable, Protocol

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
    "DeterministicRandomPriceSource",
    "HybridPriceSource",
    "PriceSource",
]
