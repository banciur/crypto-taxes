from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

import pytest
import requests

import services.open_exchange_rates_source as oxr_module
from services.open_exchange_rates_source import (
    HistoricalRates,
    OpenExchangeRatesSource,
    _OpenExchangeRatesClient,
)


class _StubResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:  # pragma: no cover - stub never raises
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _StubSession:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.last_request: dict[str, Any] | None = None

    def mount(self, prefix: str, adapter: Any) -> None:  # pragma: no cover - test helper
        return None

    def request(
        self, method: str, url: str, params: dict[str, Any] | None = None, timeout: float | None = None
    ) -> _StubResponse:
        self.last_request = {"method": method, "url": url, "params": params, "timeout": timeout}
        return _StubResponse(self._payload)


def _set_app_id(monkeypatch: pytest.MonkeyPatch, value: str = "test-app") -> None:
    monkeypatch.setattr(oxr_module, "config", lambda: SimpleNamespace(open_exchange_rates_app_id=value))


def test_open_exchange_rates_http_client_parses_historical_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_app_id(monkeypatch)
    payload = {
        "timestamp": 1704153599,
        "base": "usd",
        "rates": {"USD": 1, "EUR": 0.9},
    }
    stub_session = _StubSession(payload=payload)
    session = cast(requests.Session, stub_session)
    client = _OpenExchangeRatesClient(base_url="https://example.com", session=session, retry_attempts=0)

    snapshot = client.get_historical_rates(target_date=date(2024, 1, 1))

    assert snapshot.base == "USD"
    assert snapshot.rates["EUR"] == Decimal("0.9")
    assert stub_session.last_request == {
        "method": "GET",
        "url": "https://example.com/historical/2024-01-01.json",
        "params": {"app_id": "test-app"},
        "timeout": 10.0,
    }


class _StubOXRClient:
    def __init__(self, snapshot: HistoricalRates) -> None:
        self.snapshot = snapshot
        self.requested_dates: list[date] = []

    def get_historical_rates(self, *, target_date: date) -> HistoricalRates:
        self.requested_dates.append(target_date)
        return self.snapshot


def test_price_source_converts_cross_currency_pair() -> None:
    historical = HistoricalRates(
        date=date(2024, 1, 1),
        timestamp=datetime(2024, 1, 1, 23, 59, tzinfo=timezone.utc),
        base="USD",
        rates={
            "USD": Decimal("1"),
            "EUR": Decimal("0.9"),
            "GBP": Decimal("0.8"),
        },
    )
    stub_client = _StubOXRClient(snapshot=historical)
    client = cast(_OpenExchangeRatesClient, stub_client)
    source = OpenExchangeRatesSource(client=client, source_name="test-source")

    ts = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    quote = source.fetch_snapshot("EUR", "USD", timestamp=ts)

    assert quote.rate == Decimal("1") / Decimal("0.9")
    assert quote.base_id == "EUR"
    assert quote.quote_id == "USD"
    assert quote.valid_from == datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert quote.valid_to == datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc)
    assert stub_client.requested_dates == [date(2024, 1, 1)]


def test_price_source_raises_for_missing_currency() -> None:
    historical = HistoricalRates(
        date=date(2024, 1, 1),
        timestamp=datetime(2024, 1, 1, 23, 59, tzinfo=timezone.utc),
        base="USD",
        rates={"USD": Decimal("1")},
    )
    source = OpenExchangeRatesSource(client=cast(_OpenExchangeRatesClient, _StubOXRClient(snapshot=historical)))

    ts = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
    with pytest.raises(RuntimeError):
        source.fetch_snapshot("EUR", "USD", timestamp=ts)


@pytest.mark.skip(reason="This test requires real api key in .env")
def test_live_request() -> None:
    source = OpenExchangeRatesSource()
    ts = datetime.combine(date(2024, 1, 1), time.min, tzinfo=timezone.utc)
    quote = source.fetch_snapshot("EUR", "USD", timestamp=ts)
    from pprint import pprint

    pprint(quote)
