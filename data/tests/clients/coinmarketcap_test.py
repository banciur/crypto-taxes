# This file is completely vibed and I didn't read it.

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import requests

from clients.coinmarketcap import CoinMarketCapAPIError, CoinMarketCapClient
from domain.ledger import AssetId
from tests.constants import BTC, EUR, USD

_HIST_PATH = "/v3/cryptocurrency/quotes/historical"
_MAP_PATH = "/v1/cryptocurrency/map"
_RECENT = datetime(2026, 7, 4, 12, 3, 20, tzinfo=timezone.utc)
_OLD = datetime(2020, 1, 1, 9, 30, tzinfo=timezone.utc)


def _mock_response(payload: Any, status_code: int = 200) -> Mock:
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload
    response.text = json.dumps(payload) if isinstance(payload, (dict, list)) else str(payload)
    response.raise_for_status.return_value = None
    return response


def _http_error_response(status_code: int, payload: Any) -> Mock:
    response = _mock_response(payload, status_code=status_code)
    response.raise_for_status.side_effect = requests.HTTPError(response=response)
    return response


def _quotes_payload(*, cmc_id: int, quote: str, price: float) -> dict[str, Any]:
    return {
        "status": {"error_code": 0, "error_message": None},
        "data": {
            str(cmc_id): {
                "id": cmc_id,
                "symbol": "BTC",
                "quotes": [
                    {
                        "timestamp": "2020-01-01T00:00:00.000Z",
                        "quote": {quote: {"price": price, "timestamp": "2020-01-01T00:00:00.000Z"}},
                    }
                ],
            }
        },
    }


def _client(session: Mock, tmp_path: Path, *, high_resolution_days: int = 30, **kwargs: Any) -> CoinMarketCapClient:
    return CoinMarketCapClient(
        api_key="test-key",
        session=session,
        asset_map_path=tmp_path / "cmc_asset_map.json",
        high_resolution_days=high_resolution_days,
        **kwargs,
    )


def _write_map(tmp_path: Path, mapping: dict[str, int]) -> Path:
    path = tmp_path / "cmc_asset_map.json"
    path.write_text(json.dumps(mapping))
    return path


def test_recent_timestamp_uses_five_minute_interval(tmp_path: Path) -> None:
    _write_map(tmp_path, {"BTC": 1})
    session = Mock()
    session.get.return_value = _mock_response(_quotes_payload(cmc_id=1, quote="USD", price=42000.5))

    record = _client(session, tmp_path).fetch_record(BTC, USD, timestamp=_RECENT)

    assert record.rate == Decimal("42000.5")
    # 12:03:20 floors to 12:00:00, window is 5 minutes.
    assert record.valid_from == datetime(2026, 7, 4, 12, 0, tzinfo=timezone.utc)
    assert record.valid_to == record.valid_from + timedelta(minutes=5)
    params = session.get.call_args.kwargs["params"]
    assert params["interval"] == "5m"
    assert params["id"] == 1
    assert params["convert"] == "USD"
    assert params["time_start"] == int(record.valid_from.timestamp())


def test_old_timestamp_uses_daily_interval(tmp_path: Path) -> None:
    _write_map(tmp_path, {"BTC": 1})
    session = Mock()
    session.get.return_value = _mock_response(_quotes_payload(cmc_id=1, quote="EUR", price=7200))

    record = _client(session, tmp_path).fetch_record(BTC, EUR, timestamp=_OLD)

    assert record.rate == Decimal("7200")
    assert record.valid_from == datetime(2020, 1, 1, tzinfo=timezone.utc)
    assert record.valid_to == record.valid_from + timedelta(days=1)
    assert session.get.call_args.kwargs["params"]["interval"] == "daily"


def test_interval_selection_at_high_resolution_cutoff(tmp_path: Path) -> None:
    _write_map(tmp_path, {"BTC": 1})
    session = Mock()
    session.get.return_value = _mock_response(_quotes_payload(cmc_id=1, quote="USD", price=1))

    just_inside = datetime.now(timezone.utc) - timedelta(days=29)
    _client(session, tmp_path, high_resolution_days=30).fetch_record(BTC, USD, timestamp=just_inside)
    assert session.get.call_args.kwargs["params"]["interval"] == "5m"

    just_outside = datetime.now(timezone.utc) - timedelta(days=31)
    _client(session, tmp_path, high_resolution_days=30).fetch_record(BTC, USD, timestamp=just_outside)
    assert session.get.call_args.kwargs["params"]["interval"] == "daily"


def test_returns_none_on_empty_quotes(tmp_path: Path) -> None:
    _write_map(tmp_path, {"BTC": 1})
    session = Mock()
    session.get.return_value = _mock_response({"status": {"error_code": 0}, "data": {"1": {"id": 1, "quotes": []}}})

    record = _client(session, tmp_path).fetch_record(BTC, USD, timestamp=_OLD)
    assert record.rate is None
    assert record.valid_from == datetime(2020, 1, 1, tzinfo=timezone.utc)


def test_returns_none_on_empty_data(tmp_path: Path) -> None:
    _write_map(tmp_path, {"BTC": 1})
    session = Mock()
    session.get.return_value = _mock_response({"status": {"error_code": 0}, "data": {}})

    record = _client(session, tmp_path).fetch_record(BTC, USD, timestamp=_OLD)
    assert record.rate is None


def test_uses_id_from_asset_map(tmp_path: Path) -> None:
    _write_map(tmp_path, {"NEU": 2318})
    session = Mock()
    session.get.return_value = _mock_response(_quotes_payload(cmc_id=2318, quote="USD", price=3))

    _client(session, tmp_path).fetch_record(AssetId("neu"), USD, timestamp=_OLD)

    # Only the historical quote request is made; no symbol discovery.
    assert session.get.call_count == 1
    assert _HIST_PATH in session.get.call_args.args[0]
    assert session.get.call_args.kwargs["params"]["id"] == 2318


def test_discovers_single_candidate_and_writes_map(tmp_path: Path) -> None:
    map_path = tmp_path / "cmc_asset_map.json"
    session = Mock()
    session.get.side_effect = [
        _mock_response({"status": {"error_code": 0}, "data": [{"id": 2318, "symbol": "NEU", "name": "Neumark"}]}),
        _mock_response(_quotes_payload(cmc_id=2318, quote="USD", price=9)),
    ]

    record = _client(session, tmp_path).fetch_record(AssetId("neu"), USD, timestamp=_OLD)

    assert record.rate == Decimal("9")
    assert session.get.call_count == 2
    assert _MAP_PATH in session.get.call_args_list[0].args[0]
    assert json.loads(map_path.read_text()) == {"NEU": 2318}


def test_zero_candidate_discovery_raises(tmp_path: Path) -> None:
    session = Mock()
    session.get.return_value = _mock_response({"status": {"error_code": 0}, "data": []})

    with pytest.raises(CoinMarketCapAPIError, match="no asset for symbol WAT"):
        _client(session, tmp_path).fetch_record(AssetId("wat"), USD, timestamp=_OLD)
    assert not (tmp_path / "cmc_asset_map.json").exists()


def test_invalid_symbol_error_returns_unpriceable_record(tmp_path: Path) -> None:
    symbol = AssetId("UNI-V2")
    session = Mock()
    session.get.return_value = _http_error_response(
        400, {"status": {"error_code": 400, "error_message": f'Invalid value for "symbol": "{symbol}"'}}
    )

    record = _client(session, tmp_path).fetch_record(symbol, USD, timestamp=_OLD)

    assert record.base_id == symbol
    assert record.quote_id == USD
    assert record.rate is None
    assert record.source == "coinmarketcap"
    assert record.valid_from == datetime(2020, 1, 1, tzinfo=timezone.utc)
    assert record.valid_to == record.valid_from + timedelta(days=1)
    assert session.get.call_count == 1
    assert _MAP_PATH in session.get.call_args.args[0]
    assert not (tmp_path / "cmc_asset_map.json").exists()


def test_ambiguous_candidate_discovery_raises_with_details(tmp_path: Path) -> None:
    session = Mock()
    session.get.return_value = _mock_response(
        {
            "status": {"error_code": 0},
            "data": [
                {"id": 1, "name": "Bitcoin", "symbol": "BTC", "rank": 1, "is_active": 1, "platform": None},
                {
                    "id": 9999,
                    "name": "Wrapped BTC",
                    "symbol": "BTC",
                    "rank": 500,
                    "is_active": 1,
                    "platform": {"name": "Ethereum", "token_address": "0xabc"},
                },
            ],
        }
    )

    with pytest.raises(CoinMarketCapAPIError) as exc_info:
        _client(session, tmp_path).fetch_record(BTC, USD, timestamp=_OLD)

    message = str(exc_info.value)
    assert "2 candidates" in message
    assert "0xabc" in message
    assert "Ethereum" in message


def test_http_error_propagates(tmp_path: Path) -> None:
    _write_map(tmp_path, {"BTC": 1})
    session = Mock()
    session.get.return_value = _http_error_response(
        400, {"status": {"error_code": 400, "error_message": "Your plan allows 1 months of historical access."}}
    )

    with pytest.raises(CoinMarketCapAPIError, match="historical access"):
        _client(session, tmp_path).fetch_record(BTC, USD, timestamp=_OLD)


def test_non_zero_status_propagates(tmp_path: Path) -> None:
    _write_map(tmp_path, {"BTC": 1})
    session = Mock()
    session.get.return_value = _mock_response({"status": {"error_code": 1001, "error_message": "Invalid API key"}})

    with pytest.raises(CoinMarketCapAPIError, match="Invalid API key"):
        _client(session, tmp_path).fetch_record(BTC, USD, timestamp=_OLD)


def test_missing_convert_currency_propagates(tmp_path: Path) -> None:
    _write_map(tmp_path, {"BTC": 1})
    session = Mock()
    # Quote present, but keyed by a different currency than requested.
    session.get.return_value = _mock_response(_quotes_payload(cmc_id=1, quote="GBP", price=1))

    with pytest.raises(CoinMarketCapAPIError, match="missing convert currency USD"):
        _client(session, tmp_path).fetch_record(BTC, USD, timestamp=_OLD)


def test_request_exception_propagates(tmp_path: Path) -> None:
    _write_map(tmp_path, {"BTC": 1})
    session = Mock()
    session.get.side_effect = requests.ConnectionError("network down")

    with pytest.raises(CoinMarketCapAPIError, match="request failed"):
        _client(session, tmp_path).fetch_record(BTC, USD, timestamp=_OLD)


def test_asset_resolution_failure_is_not_negative_cached(tmp_path: Path) -> None:
    """A zero-candidate discovery must raise, never return a ``rate=None`` record.

    PriceService only negative-caches genuine ``None`` records, so raising here guarantees the
    unresolved symbol never poisons the cache.
    """
    session = Mock()
    session.get.return_value = _mock_response({"status": {"error_code": 0}, "data": []})

    with pytest.raises(CoinMarketCapAPIError):
        _client(session, tmp_path).fetch_record(AssetId("wat"), USD, timestamp=_OLD)


@pytest.mark.skip(reason="This test requires real api key in .env")
def test_live_request() -> None:
    from pprint import pprint

    from config import config

    client = CoinMarketCapClient(api_key=config().coinmarketcap_api_key)
    record = client.fetch_record(BTC, USD, timestamp=datetime.now(timezone.utc) - timedelta(hours=1))
    pprint(record)
