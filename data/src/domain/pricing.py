from datetime import datetime
from decimal import Decimal
from typing import Protocol

from errors import CryptoTaxesError

from .ledger import AssetId


class RequiredPriceUnavailableError(CryptoTaxesError):
    def __init__(
        self,
        *,
        base_id: AssetId,
        quote_id: AssetId,
        timestamp: datetime,
        reason: str,
    ) -> None:
        super().__init__(
            f"Required price unavailable: base={base_id} quote={quote_id} timestamp={timestamp.isoformat()}. {reason}"
        )
        self.base_id = base_id
        self.quote_id = quote_id
        self.timestamp = timestamp
        self.reason = reason


class PriceProvider(Protocol):
    """Lookup interface for asset→quote rates."""

    def rate(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> Decimal: ...
