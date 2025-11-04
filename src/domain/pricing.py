from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, model_validator


class PriceSnapshot(BaseModel):
    """Unified market/FX price snapshot.

    Represents the rate of `base_id` quoted in `quote_id` at a specific
    timestamp. Works for crypto-crypto, crypto-fiat, and fiat-fiat pairs.
    - `rate` means: 1 base_id = rate quote_id.
    """

    timestamp: datetime
    base_id: str
    quote_id: str
    rate: Decimal
    source: str

    @model_validator(mode="after")
    def _validate(self) -> PriceSnapshot:
        if self.base_id == self.quote_id:
            raise ValueError("base_id and quote_id must differ")
        if self.rate <= 0:
            raise ValueError("rate must be > 0")
        return self

    def invert(self, *, new_source: str | None = None) -> PriceSnapshot:
        """Return the inverted pair (quote/base) with a reciprocal rate."""
        return PriceSnapshot(
            timestamp=self.timestamp,
            base_id=self.quote_id,
            quote_id=self.base_id,
            rate=(Decimal(1) / self.rate),
            source=new_source or self.source,
        )


class PriceProvider(Protocol):
    """Lookup interface for asset→quote rates."""

    def rate(self, base_id: str, quote_id: str, timestamp: datetime) -> Decimal: ...


__all__ = ["PriceProvider", "PriceSnapshot"]
