from datetime import datetime, timedelta

from clients.coindesk import CoinDeskClient, fetch_histo_candles
from domain.ledger import AssetId

from .price_sources import PriceSnapshotSource
from .price_types import PriceQuote


class CoinDeskSource(PriceSnapshotSource):
    def __init__(
        self,
        *,
        market: str = "coinbase",
        aggregate_minutes: int = 60,
        client: CoinDeskClient | None = None,
        source_name: str = "coindesk-spot-api",
    ) -> None:
        if aggregate_minutes <= 0:
            msg = "aggregate_minutes must be greater than 0"
            raise ValueError(msg)
        if aggregate_minutes < 60 and aggregate_minutes > 30:
            msg = "CoinDesk minute candles support aggregate_minutes up to 30"
            raise ValueError(msg)
        if aggregate_minutes >= 60 and aggregate_minutes % 60 != 0:
            msg = "aggregate_minutes must be divisible by 60 when requesting hour candles"
            raise ValueError(msg)

        if not market:
            msg = "market must be provided"
            raise ValueError(msg)

        self.client = client or CoinDeskClient()
        self.market = market
        self.aggregate_minutes = aggregate_minutes
        self.source_name = source_name
        self._bucket_duration = timedelta(minutes=aggregate_minutes)

    def fetch_snapshot(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> PriceQuote | None:
        instrument = f"{base_id.upper()}-{quote_id.upper()}"
        entries, override_valid_from = fetch_histo_candles(
            client=self.client,
            market=self.market,
            instrument=instrument,
            timestamp=timestamp,
            aggregate_minutes=self.aggregate_minutes,
        )

        if not entries:
            return None

        bucket = max(entries, key=lambda entry: entry.timestamp)
        valid_from = override_valid_from or bucket.timestamp
        valid_to = valid_from + self._bucket_duration

        return PriceQuote(
            timestamp=valid_from,
            base_id=AssetId(base_id.upper()),
            quote_id=AssetId(quote_id.upper()),
            rate=bucket.close,
            source=self.source_name,
            valid_from=valid_from,
            valid_to=valid_to,
        )
