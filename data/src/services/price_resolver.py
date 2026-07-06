from datetime import datetime

from config import FIAT_CURRENCY_CODES
from domain.ledger import AssetId
from domain.pricing import PriceRecord, PriceSource


class PriceResolver(PriceSource):
    def __init__(self, *, crypto_source: PriceSource, fiat_source: PriceSource) -> None:
        self.crypto_source = crypto_source
        self.fiat_source = fiat_source

    def fetch_record(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> PriceRecord:
        base = AssetId(base_id.upper())
        quote = AssetId(quote_id.upper())
        return self._source_for(base).fetch_record(base, quote, timestamp)

    def _source_for(self, asset: AssetId) -> PriceSource:
        if asset in FIAT_CURRENCY_CODES:
            return self.fiat_source
        return self.crypto_source
