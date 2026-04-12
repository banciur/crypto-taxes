from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from domain.ledger import AssetId


@dataclass(frozen=True)
class PriceQuote:
    timestamp: datetime
    base_id: AssetId
    quote_id: AssetId
    rate: Decimal
    source: str
    valid_from: datetime
    valid_to: datetime
