from __future__ import annotations

import hashlib
import random
from datetime import datetime
from decimal import Decimal

from domain.pricing import PriceProvider
from services.price_sources import PriceSnapshotSource
from services.price_types import PriceQuote


class DeterministicRandomPriceSource(PriceSnapshotSource):
    def __init__(
        self,
        *,
        seed: int = 0,
        min_price: Decimal = Decimal("10"),
        max_price: Decimal = Decimal("70000"),
        source_name: str = "test-deterministic-rng",
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


class TestPriceService(PriceProvider):
    __test__ = False

    def __init__(
        self,
        *,
        seed: int = 0,
        min_price: Decimal = Decimal("10"),
        max_price: Decimal = Decimal("70000"),
        source_name: str = "test-price-service",
    ) -> None:
        self._source = DeterministicRandomPriceSource(
            seed=seed,
            min_price=min_price,
            max_price=max_price,
            source_name=source_name,
        )

    def rate(self, base_id: str, quote_id: str, timestamp: datetime) -> Decimal:
        snapshot = self._source.fetch_snapshot(base_id=base_id, quote_id=quote_id, timestamp=timestamp)
        return snapshot.rate


__all__ = ["TestPriceService"]
