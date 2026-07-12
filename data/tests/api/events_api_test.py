from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from accounts import KRAKEN_ACCOUNT_ID
from domain.ledger import EventLocation, LedgerEvent, LedgerLeg
from tests.api.conftest import raw_event
from tests.constants import ETH, EUR, USDC

TIMESTAMP = datetime(2024, 2, 3, 10, 0, tzinfo=timezone.utc)


def _eth_event(external_id: str) -> LedgerEvent:
    return raw_event(
        location=EventLocation.BASE,
        external_id=external_id,
        timestamp=TIMESTAMP,
        legs=[
            LedgerLeg(asset_id=ETH, quantity=Decimal("1"), account_chain_id=KRAKEN_ACCOUNT_ID),
            LedgerLeg(asset_id=EUR, quantity=Decimal("-2500"), account_chain_id=KRAKEN_ACCOUNT_ID),
        ],
    )


def _usdc_event(external_id: str) -> LedgerEvent:
    return raw_event(
        location=EventLocation.BASE,
        external_id=external_id,
        timestamp=TIMESTAMP,
        legs=[
            LedgerLeg(asset_id=USDC, quantity=Decimal("100"), account_chain_id=KRAKEN_ACCOUNT_ID),
            LedgerLeg(asset_id=EUR, quantity=Decimal("-92"), account_chain_id=KRAKEN_ACCOUNT_ID),
        ],
    )


def test_get_raw_events_includes_note(
    client: TestClient,
    persist_raw_events: Callable[[list[LedgerEvent]], None],
) -> None:
    note = "approve"
    persist_raw_events(
        [
            raw_event(
                location=EventLocation.BASE,
                external_id="0xraw-note",
                timestamp=TIMESTAMP,
                note=note,
            )
        ]
    )

    response = client.get("/raw-events")

    assert response.status_code == 200
    assert response.json()[0]["note"] == note


def test_get_corrected_events_includes_note(
    client: TestClient,
    persist_corrected_events: Callable[[list[LedgerEvent]], None],
) -> None:
    note = "depositAll"
    persist_corrected_events(
        [
            raw_event(
                location=EventLocation.OPTIMISM,
                external_id="0xcorrected-note",
                timestamp=TIMESTAMP,
                note=note,
            )
        ]
    )

    response = client.get("/corrected-events")

    assert response.status_code == 200
    assert response.json()[0]["note"] == note


def test_get_raw_events_filtered_by_asset_returns_only_matching_events(
    client: TestClient,
    persist_raw_events: Callable[[list[LedgerEvent]], None],
) -> None:
    eth_event = _eth_event("0xeth")
    persist_raw_events([eth_event, _usdc_event("0xusdc")])

    response = client.get("/raw-events", params={"asset": ETH})

    assert response.status_code == 200
    assert [event["event_origin"]["external_id"] for event in response.json()] == [eth_event.event_origin.external_id]


def test_get_raw_events_filtered_by_asset_keeps_every_leg_of_a_matching_event(
    client: TestClient,
    persist_raw_events: Callable[[list[LedgerEvent]], None],
) -> None:
    eth_event = _eth_event("0xeth")
    persist_raw_events([eth_event])

    response = client.get("/raw-events", params={"asset": ETH})

    assert response.status_code == 200
    assert {leg["asset_id"] for leg in response.json()[0]["legs"]} == {leg.asset_id for leg in eth_event.legs}


def test_get_raw_events_filtered_by_unknown_asset_returns_nothing(
    client: TestClient,
    persist_raw_events: Callable[[list[LedgerEvent]], None],
) -> None:
    persist_raw_events([_eth_event("0xeth")])

    response = client.get("/raw-events", params={"asset": "DOGE"})

    assert response.status_code == 200
    assert response.json() == []


def test_get_raw_events_trims_the_asset(
    client: TestClient,
    persist_raw_events: Callable[[list[LedgerEvent]], None],
) -> None:
    eth_event = _eth_event("0xeth")
    persist_raw_events([eth_event, _usdc_event("0xusdc")])

    response = client.get("/raw-events", params={"asset": f"  {ETH}  "})

    assert response.status_code == 200
    assert [event["event_origin"]["external_id"] for event in response.json()] == [eth_event.event_origin.external_id]


def test_get_raw_events_rejects_a_blank_asset(client: TestClient) -> None:
    empty_response = client.get("/raw-events", params={"asset": ""})
    whitespace_response = client.get("/raw-events", params={"asset": "  "})

    assert empty_response.status_code == 422
    assert whitespace_response.status_code == 422


def test_get_corrected_events_filtered_by_asset_returns_only_matching_events(
    client: TestClient,
    persist_corrected_events: Callable[[list[LedgerEvent]], None],
) -> None:
    eth_event = _eth_event("0xeth")
    persist_corrected_events([eth_event, _usdc_event("0xusdc")])

    response = client.get("/corrected-events", params={"asset": ETH})

    assert response.status_code == 200
    assert [event["event_origin"]["external_id"] for event in response.json()] == [eth_event.event_origin.external_id]
