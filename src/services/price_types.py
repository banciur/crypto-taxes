from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class PriceQuote:
    timestamp: datetime
    base_id: str
    quote_id: str
    rate: Decimal
    source: str
    valid_from: datetime
    valid_to: datetime
