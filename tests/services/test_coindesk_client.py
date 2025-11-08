from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest
import requests

from services.coindesk_client import CoinDeskAPIError, CoinDeskClient


def _mock_response(payload: dict, status_code: int = 200) -> Mock:
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload
    response.text = "payload"
    response.raise_for_status.return_value = None
    return response


def test_get_spot_historical_minutes_parses_response() -> None:
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

    client = CoinDeskClient(api_key="token", session=session)
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


def test_get_spot_historical_hours_parses_response() -> None:
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

    client = CoinDeskClient(api_key="token", session=session)
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


def test_get_spot_historical_minutes_raises_on_api_error() -> None:
    session = Mock()
    payload = {"Data": [], "Err": {"message": "Invalid market"}}
    session.request.return_value = _mock_response(payload)

    client = CoinDeskClient(api_key="token", session=session)
    with pytest.raises(CoinDeskAPIError):
        client.get_spot_historical_minutes(market="bad", instrument="BTC-USD", to_ts=123)


def test_request_wraps_http_errors() -> None:
    session = Mock()
    response = _mock_response({}, status_code=429)
    http_error = requests.HTTPError(response=response)
    response.raise_for_status.side_effect = http_error
    session.request.return_value = response

    client = CoinDeskClient(api_key="token", session=session)

    with pytest.raises(CoinDeskAPIError):
        client.get_spot_historical_minutes(market="coinbase", instrument="BTC-USD", to_ts=1)
