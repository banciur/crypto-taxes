from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol

from .ledger import AssetId


class RequiredPriceUnavailableError(Exception):
    """Raised when the system requires a direct price and the price service cannot provide it."""


class PriceProvider(Protocol):
    """Lookup interface for asset→quote rates."""

    def rate(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> Decimal: ...
