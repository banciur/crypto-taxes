from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import cast
from unittest.mock import Mock

import pytest
import requests

from services.coindesk_source import (
    CoinDeskAPIError,
    CoinDeskSource,
    SpotInstrumentOHLC,
    _CoinDeskClient,
    fetch_spot_candle,
    fetch_spot_history,
)
from tests.constants import BTC, USD
from tests.services.constants import BTC_LOWER, ETHW_LOWER, EUR_LOWER, USD_LOWER


class _StubCoinDeskClient:
    def __init__(self, entries: list[SpotInstrumentOHLC]) -> None:
        self.entries = entries
        self.captured_minutes_params: dict[str, object] | None = None
        self.captured_hours_params: dict[str, object] | None = None

    def get_spot_historical_minutes(self, **params: object) -> list[SpotInstrumentOHLC]:
        self.captured_minutes_params = params
        return self.entries

    def get_spot_historical_hours(self, **params: object) -> list[SpotInstrumentOHLC]:
        self.captured_hours_params = params
        return self.entries

    def get_market_instrument(self, **params: object) -> dict | None:
        return None


def test_coindesk_source_transforms_hour_bucket_into_quote() -> None:
    bucket_start = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    entry = SpotInstrumentOHLC(
        timestamp=bucket_start,
        market="coinbase",
        instrument="BTCUSD",
        mapped_instrument="BTC-USD",
        base_asset="BTC",
        quote_asset="USD",
        open=Decimal("42000"),
        high=Decimal("42100"),
        low=Decimal("41900"),
        close=Decimal("42050.12"),
        volume=Decimal("10"),
        quote_volume=Decimal("420501.2"),
    )
    client = _StubCoinDeskClient([entry])

    source = CoinDeskSource(client=cast(_CoinDeskClient, client), market="coinbase")
    quote = source.fetch_snapshot(BTC_LOWER, USD_LOWER, timestamp=bucket_start)

    assert quote is not None
    assert quote.rate == Decimal("42050.12")
    assert quote.valid_from == bucket_start
    assert quote.valid_to == bucket_start + timedelta(minutes=60)
    assert client.captured_hours_params is not None
    assert client.captured_minutes_params is None
    assert client.captured_hours_params["instrument"] == "BTC-USD"
    assert client.captured_hours_params["aggregate"] == 1


def test_coindesk_source_supports_minute_buckets() -> None:
    bucket_start = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    entry = SpotInstrumentOHLC(
        timestamp=bucket_start,
        market="coinbase",
        instrument="BTCUSD",
        mapped_instrument="BTC-USD",
        base_asset="BTC",
        quote_asset="USD",
        open=Decimal("42000"),
        high=Decimal("42100"),
        low=Decimal("41900"),
        close=Decimal("42050.12"),
        volume=Decimal("10"),
        quote_volume=Decimal("420501.2"),
    )
    client = _StubCoinDeskClient([entry])

    source = CoinDeskSource(client=cast(_CoinDeskClient, client), market="coinbase", aggregate_minutes=15)
    quote = source.fetch_snapshot(BTC_LOWER, USD_LOWER, timestamp=bucket_start)

    assert quote is not None
    assert quote.valid_to == bucket_start + timedelta(minutes=15)
    assert client.captured_minutes_params is not None
    assert client.captured_minutes_params["aggregate"] == 15
    assert client.captured_hours_params is None


def test_coindesk_source_rejects_unsupported_bucket_lengths() -> None:
    client = cast(_CoinDeskClient, _StubCoinDeskClient([]))
    with pytest.raises(ValueError):
        CoinDeskSource(client=client, market="coinbase", aggregate_minutes=45)


def test_coindesk_source_returns_none_when_price_data_is_unavailable() -> None:
    requested_timestamp = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    client = cast(_CoinDeskClient, _StubCoinDeskClient([]))
    source = CoinDeskSource(client=client, market="coinbase")

    assert source.fetch_snapshot(BTC_LOWER, USD_LOWER, timestamp=requested_timestamp) is None


def test_fetch_spot_history_pages_backwards_and_returns_ascending_range() -> None:
    bucket_base = datetime(2025, 1, 1, 8, 0, tzinfo=timezone.utc)
    entries_by_to_ts = {
        int((bucket_base + timedelta(hours=4)).timestamp()): [
            _entry(bucket_base + timedelta(hours=2)),
            _entry(bucket_base + timedelta(hours=3)),
        ],
        int((bucket_base + timedelta(hours=1)).timestamp()): [
            _entry(bucket_base),
            _entry(bucket_base + timedelta(hours=1)),
        ],
    }

    class _PagingClient(_StubCoinDeskClient):
        def __init__(self) -> None:
            super().__init__([])
            self.captured_to_ts: list[int] = []

        def get_spot_historical_hours(self, **params: object) -> list[SpotInstrumentOHLC]:
            to_ts = cast(int, params["to_ts"])
            self.captured_to_ts.append(to_ts)
            return entries_by_to_ts.get(to_ts, [])

    client = _PagingClient()
    from_timestamp = bucket_base + timedelta(hours=1)
    to_timestamp = bucket_base + timedelta(hours=4)

    entries = fetch_spot_history(
        client=cast(_CoinDeskClient, client),
        market="coinbase",
        instrument="ETH-EUR",
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
        page_limit=2,
    )

    assert [entry.timestamp for entry in entries] == [
        bucket_base + timedelta(hours=1),
        bucket_base + timedelta(hours=2),
        bucket_base + timedelta(hours=3),
    ]
    assert client.captured_to_ts == [
        int(to_timestamp.timestamp()),
        int(bucket_base.timestamp()) + 3600,
    ]


def test_fetch_spot_history_uses_minute_endpoint_for_sub_hour_buckets() -> None:
    bucket_start = datetime(2025, 1, 1, 12, 15, tzinfo=timezone.utc)
    entry = _entry(bucket_start)

    class _MinuteClient(_StubCoinDeskClient):
        def get_spot_historical_minutes(self, **params: object) -> list[SpotInstrumentOHLC]:
            self.captured_minutes_params = params
            return [entry]

    client = _MinuteClient([])
    entries = fetch_spot_history(
        client=cast(_CoinDeskClient, client),
        market="coinbase",
        instrument="ETH-EUR",
        from_timestamp=bucket_start,
        to_timestamp=bucket_start + timedelta(minutes=15),
        aggregate_minutes=15,
        page_limit=10,
    )

    assert entries == [entry]
    assert client.captured_minutes_params is not None
    assert client.captured_minutes_params["aggregate"] == 15
    assert client.captured_hours_params is None


def test_fetch_spot_history_clamps_page_limit_to_api_max_for_aggregate() -> None:
    bucket_start = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    entry = _entry(bucket_start)

    class _ClampedClient(_StubCoinDeskClient):
        def get_spot_historical_hours(self, **params: object) -> list[SpotInstrumentOHLC]:
            self.captured_hours_params = params
            return [entry]

    client = _ClampedClient([])
    fetch_spot_history(
        client=cast(_CoinDeskClient, client),
        market="coinbase",
        instrument="ETH-EUR",
        from_timestamp=bucket_start,
        to_timestamp=bucket_start + timedelta(days=1),
        aggregate_minutes=1_440,
        page_limit=2_000,
    )

    assert client.captured_hours_params is not None
    assert client.captured_hours_params["aggregate"] == 24
    assert client.captured_hours_params["limit"] == 83


def test_fetch_spot_candle_returns_latest_bucket_for_timestamp() -> None:
    requested_timestamp = datetime(2025, 1, 1, 12, 34, tzinfo=timezone.utc)
    entry = _entry(datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc))

    class _SingleBucketClient(_StubCoinDeskClient):
        def get_spot_historical_hours(self, **params: object) -> list[SpotInstrumentOHLC]:
            self.captured_hours_params = params
            return [entry]

    client = _SingleBucketClient([])
    result = fetch_spot_candle(
        client=cast(_CoinDeskClient, client),
        market="coinbase",
        instrument="ETH-EUR",
        timestamp=requested_timestamp,
    )

    assert result == entry
    assert client.captured_hours_params is not None
    assert client.captured_hours_params["to_ts"] == int(requested_timestamp.timestamp())
    assert client.captured_hours_params["limit"] == 1


def _mock_response(payload: dict, status_code: int = 200) -> Mock:
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload
    response.text = "payload"
    response.raise_for_status.return_value = None
    return response


def _http_error_response(status_code: int) -> Mock:
    response = _mock_response({}, status_code=status_code)
    http_error = requests.HTTPError(response=response)
    response.raise_for_status.side_effect = http_error
    return response


def test_coindesk_http_client_parses_minutes_payload() -> None:
    session = Mock()
    payload = {
        "Data": [
            {
                "TIMESTAMP": 1_700_000_000,
                "MARKET": "coinbase",
                "INSTRUMENT": "BTCUSD",
                "MAPPED_INSTRUMENT": "BTC-USD",
                "BASE": "BTC",
                "QUOTE": "USD",
                "OPEN": 100,
                "HIGH": 110,
                "LOW": 90,
                "CLOSE": 105.5,
                "VOLUME": 12.3,
                "QUOTE_VOLUME": 123_456,
            }
        ],
        "Err": {},
    }
    session.request.return_value = _mock_response(payload)

    client = _CoinDeskClient(session=session, retry_attempts=0)
    entries = client.get_spot_historical_minutes(
        market="coinbase",
        instrument="BTC-USD",
        to_ts=1_700_000_010,
    )

    assert len(entries) == 1
    entry = entries[0]
    assert entry.close == Decimal("105.5")
    assert entry.base_asset == "BTC"
    assert entry.quote_asset == "USD"
    assert entry.timestamp == datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc)

    session.request.assert_called_once()
    kwargs = session.request.call_args.kwargs
    assert kwargs["params"]["instrument"] == "BTC-USD"
    assert kwargs["params"]["market"] == "coinbase"


def test_coindesk_http_client_parses_hour_payload() -> None:
    session = Mock()
    payload = {
        "Data": [
            {
                "TIMESTAMP": 1_700_000_000,
                "MARKET": "coinbase",
                "INSTRUMENT": "BTCUSD",
                "CLOSE": 100,
            }
        ],
        "Err": {},
    }
    session.request.return_value = _mock_response(payload)

    client = _CoinDeskClient(session=session)
    entries = client.get_spot_historical_hours(
        market="coinbase",
        instrument="BTC-USD",
        to_ts=1_700_000_010,
    )

    assert len(entries) == 1
    session.request.assert_called_once()
    args, kwargs = session.request.call_args
    assert "/spot/v1/historical/hours" in args[1]
    assert kwargs["params"]["aggregate"] == 1


def test_coindesk_http_client_raises_on_api_error() -> None:
    session = Mock()
    payload = {"Data": [], "Err": {"message": "Invalid market"}}
    session.request.return_value = _mock_response(payload)

    client = _CoinDeskClient(session=session)
    with pytest.raises(CoinDeskAPIError):
        client.get_spot_historical_minutes(market="bad", instrument="BTC-USD", to_ts=123)


def test_coindesk_http_client_wraps_http_errors() -> None:
    session = Mock()
    response = _http_error_response(429)
    session.request.return_value = response

    client = _CoinDeskClient(session=session)

    with pytest.raises(CoinDeskAPIError):
        client.get_spot_historical_minutes(market="coinbase", instrument="BTC-USD", to_ts=1)


def test_coindesk_source_retries_with_first_trade_timestamp() -> None:
    bucket_start = datetime(2022, 9, 16, 10, 0, tzinfo=timezone.utc)
    earlier = bucket_start - timedelta(hours=1)
    entry = SpotInstrumentOHLC(
        timestamp=bucket_start,
        market="kraken",
        instrument="ETHWEUR",
        mapped_instrument="ETHW-EUR",
        base_asset="ETHW",
        quote_asset="EUR",
        open=Decimal("10"),
        high=Decimal("11"),
        low=Decimal("9"),
        close=Decimal("10.5"),
        volume=Decimal("1"),
        quote_volume=Decimal("10.5"),
    )

    class _FallbackClient(_StubCoinDeskClient):
        def __init__(self) -> None:
            super().__init__([entry])
            self._fail_once = True
            self.instrument_lookup: tuple[str, str] | None = None

        def get_spot_historical_hours(self, **params: object) -> list[SpotInstrumentOHLC]:
            if self._fail_once:
                self._fail_once = False
                raise CoinDeskAPIError(
                    "Invalid: to_ts parameter ... FIRST_TRADE_SPOT_TIMESTAMP",
                    status_code=404,
                )
            return super().get_spot_historical_hours(**params)

        def get_market_instrument(self, **params: object) -> dict | None:
            market = cast(str, params["market"])
            instrument = cast(str, params["instrument"])
            self.instrument_lookup = (market, instrument)
            return {"FIRST_TRADE_SPOT_TIMESTAMP": int(bucket_start.timestamp())}

    fallback_client = _FallbackClient()
    source = CoinDeskSource(client=cast(_CoinDeskClient, fallback_client), market="kraken")

    quote = source.fetch_snapshot(ETHW_LOWER, EUR_LOWER, timestamp=earlier)

    assert quote is not None
    assert quote.rate == Decimal("10.5")
    assert quote.valid_from == earlier
    assert quote.valid_to == earlier + timedelta(minutes=60)
    assert fallback_client.captured_hours_params is not None
    assert fallback_client.captured_hours_params["to_ts"] == int(bucket_start.timestamp())
    assert fallback_client.instrument_lookup == ("kraken", "ETHW-EUR")


def _entry(timestamp: datetime) -> SpotInstrumentOHLC:
    return SpotInstrumentOHLC(
        timestamp=timestamp,
        market="coinbase",
        instrument="ETHEUR",
        mapped_instrument="ETH-EUR",
        base_asset="ETH",
        quote_asset="EUR",
        open=Decimal("2500"),
        high=Decimal("2550"),
        low=Decimal("2450"),
        close=Decimal("2525"),
        volume=Decimal("1"),
        quote_volume=Decimal("2525"),
    )


@pytest.mark.skip(reason="This test requires real api key in .env")
def test_live_request() -> None:
    source = CoinDeskSource()
    ts = datetime.now(timezone.utc)
    quote = source.fetch_snapshot(
        BTC,
        USD,
        timestamp=ts,
    )
    from pprint import pprint

    pprint(quote)
