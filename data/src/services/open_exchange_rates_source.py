from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from clients.open_exchange_rates import HistoricalRates, OpenExchangeRatesClient
from domain.ledger import AssetId

from .price_sources import PriceSnapshotSource
from .price_types import PriceQuote


class OpenExchangeRatesSource(PriceSnapshotSource):
    def __init__(
        self,
        *,
        client: OpenExchangeRatesClient | None = None,
        source_name: str = "open-exchange-rates-historical",
    ) -> None:
        self.client = client or OpenExchangeRatesClient()
        self.source_name = source_name

    def fetch_snapshot(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> PriceQuote | None:
        snapshot = self.client.get_historical_rates(target_date=timestamp.date())

        base = AssetId(base_id.upper())
        quote = AssetId(quote_id.upper())

        rate = self._compute_rate(snapshot=snapshot, base=base, quote=quote)
        if rate is None:
            return None

        valid_from = datetime.combine(snapshot.date, time.min, tzinfo=timezone.utc)
        valid_to = valid_from + timedelta(days=1)

        return PriceQuote(
            timestamp=snapshot.timestamp,
            base_id=base,
            quote_id=quote,
            rate=rate,
            source=self.source_name,
            valid_from=valid_from,
            valid_to=valid_to,
        )

    def _compute_rate(
        self,
        *,
        snapshot: HistoricalRates,
        base: AssetId,
        quote: AssetId,
    ) -> Decimal | None:
        if base == quote:
            return Decimal("1")

        try:
            base_rate = self._resolve_rate(snapshot=snapshot, currency=base)
            quote_rate = self._resolve_rate(snapshot=snapshot, currency=quote)
        except KeyError:
            return None
        return quote_rate / base_rate

    @staticmethod
    def _resolve_rate(*, snapshot: HistoricalRates, currency: AssetId) -> Decimal:
        if currency == snapshot.base:
            return Decimal("1")
        return snapshot.rates[currency]
