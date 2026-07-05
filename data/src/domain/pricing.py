from datetime import datetime
from decimal import Decimal
from typing import Protocol

from .ledger import AssetId


class PriceProvider(Protocol):
    def rate(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> Decimal | None: ...
