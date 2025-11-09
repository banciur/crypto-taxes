from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import cast
from unittest.mock import Mock

import pytest
import requests

from services.coindesk_source import CoinDeskAPIError, CoinDeskSource, SpotInstrumentOHLC, _CoinDeskClient


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
    quote = source.fetch_snapshot("btc", "usd", timestamp=bucket_start)

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
    quote = source.fetch_snapshot("btc", "usd", timestamp=bucket_start)

    assert quote.valid_to == bucket_start + timedelta(minutes=15)
    assert client.captured_minutes_params is not None
    assert client.captured_minutes_params["aggregate"] == 15
    assert client.captured_hours_params is None


def test_coindesk_source_rejects_unsupported_bucket_lengths() -> None:
    client = cast(_CoinDeskClient, _StubCoinDeskClient([]))
    with pytest.raises(ValueError):
        CoinDeskSource(client=client, market="coinbase", aggregate_minutes=45)


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


@pytest.mark.skip(reason="This test requires real api key in .env")
def test_live_request() -> None:
    source = CoinDeskSource()
    ts = datetime.now(timezone.utc)
    quote = source.fetch_snapshot(
        "BTC",
        "USD",
        timestamp=ts,
    )
    from pprint import pprint
    pprint(quote)
