from datetime import datetime
from typing import Iterable

from domain.ledger import AssetId
from domain.pricing import PriceRecord, PriceSource


class PriceResolver:
    def __init__(
        self,
        *,
        crypto_source: PriceSource,
        fiat_source: PriceSource,
        fiat_currency_codes: Iterable[str] | None = None,
    ) -> None:
        self.crypto_source = crypto_source
        self.fiat_source = fiat_source
        fiat_codes = {code.upper() for code in (fiat_currency_codes or ("EUR", "USD"))}
        if not fiat_codes:
            msg = "fiat_currency_codes must contain at least one entry"
            raise ValueError(msg)
        self._fiat_codes = frozenset(fiat_codes)

    def resolve(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> PriceRecord:
        base = AssetId(base_id.upper())
        quote = AssetId(quote_id.upper())
        return self._source_for(base, quote).fetch_record(base, quote, timestamp)

    def _source_for(self, base_id: AssetId, quote_id: AssetId) -> PriceSource:
        if self._is_fiat_pair(base_id, quote_id):
            return self.fiat_source
        return self.crypto_source

    def _is_fiat_pair(self, base_id: AssetId, quote_id: AssetId) -> bool:
        return base_id.upper() in self._fiat_codes and quote_id.upper() in self._fiat_codes
