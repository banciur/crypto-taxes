from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol


class PriceProvider(Protocol):
    """Lookup interface for asset→quote rates."""

    def rate(self, base_id: str, quote_id: str, timestamp: datetime) -> Decimal: ...
