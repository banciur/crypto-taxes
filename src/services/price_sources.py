from __future__ import annotations

from datetime import datetime
from typing import Iterable, Protocol

from .price_types import PriceQuote


class PriceSnapshotSource(Protocol):
    def fetch_snapshot(self, base_id: str, quote_id: str, timestamp: datetime) -> PriceQuote: ...


class HybridPriceSource(PriceSnapshotSource):
    def __init__(
        self,
        *,
        crypto_source: PriceSnapshotSource,
        fiat_source: PriceSnapshotSource,
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
    "HybridPriceSource",
    "PriceSnapshotSource",
]
