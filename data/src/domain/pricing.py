from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from .ledger import AssetId


@dataclass(frozen=True)
class PriceRecord:
    base_id: AssetId
    quote_id: AssetId
    rate: Decimal | None
    source: str
    valid_from: datetime
    valid_to: datetime
    fetched_at: datetime


class PriceProvider(Protocol):
    def rate(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> Decimal | None: ...


class PriceSource(Protocol):
    def fetch_record(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> PriceRecord: ...


class PriceCache(Protocol):
    def write(self, record: PriceRecord) -> None: ...

    def read(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> PriceRecord | None: ...
