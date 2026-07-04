from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from accounts import KRAKEN_ACCOUNT_ID
from db.acquisition_disposal import AcquisitionDisposalProjectionRepository
from domain.acquisition_disposal.models import AcquisitionLot, DisposalLink
from domain.acquisition_disposal.projector import AcquisitionDisposalProjection
from domain.ledger import EventLocation, EventOrigin
from tests.constants import BTC


@pytest.fixture()
def persist_acquisition_disposal_projection(
    client: TestClient,
) -> Callable[[AcquisitionDisposalProjection], None]:
    def persist(projection: AcquisitionDisposalProjection) -> None:
        app = cast(FastAPI, client.app)
        with app.state.sessionmaker() as session:
            AcquisitionDisposalProjectionRepository(session).replace(projection)

    return persist


def _acquisition_lot(
    *,
    external_id: str,
    timestamp: datetime,
    quantity_acquired: Decimal,
    cost_per_unit: Decimal,
) -> AcquisitionLot:
    return AcquisitionLot(
        event_origin=EventOrigin(location=EventLocation.KRAKEN, external_id=external_id),
        account_chain_id=KRAKEN_ACCOUNT_ID,
        asset_id=BTC,
        is_fee=False,
        timestamp=timestamp,
        quantity_acquired=quantity_acquired,
        cost_per_unit=cost_per_unit,
    )


def _disposal_link(
    *,
    lot: AcquisitionLot,
    external_id: str,
    timestamp: datetime,
    quantity_used: Decimal,
    proceeds_total: Decimal,
) -> DisposalLink:
    return DisposalLink(
        event_origin=EventOrigin(location=EventLocation.KRAKEN, external_id=external_id),
        account_chain_id=KRAKEN_ACCOUNT_ID,
        asset_id=BTC,
        is_fee=False,
        timestamp=timestamp,
        lot_id=lot.id,
        quantity_used=quantity_used,
        proceeds_total=proceeds_total,
    )


def test_get_acquisition_disposal_returns_empty_feed_when_projection_is_missing(client: TestClient) -> None:
    response = client.get("/acquisition-disposal")

    assert response.status_code == 200
    assert response.json() == []


def test_get_acquisition_disposal_returns_acquisition_item(
    client: TestClient,
    persist_acquisition_disposal_projection: Callable[[AcquisitionDisposalProjection], None],
) -> None:
    timestamp = datetime(2024, 1, 4, 9, 0, 0, tzinfo=timezone.utc)
    quantity_acquired = Decimal("0.5")
    cost_per_unit = Decimal("20000")
    lot = _acquisition_lot(
        external_id="acq-ext",
        timestamp=timestamp,
        quantity_acquired=quantity_acquired,
        cost_per_unit=cost_per_unit,
    )
    persist_acquisition_disposal_projection(AcquisitionDisposalProjection(acquisition_lots=[lot], disposal_links=[]))

    response = client.get("/acquisition-disposal")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(lot.id),
            "timestamp": "2024-01-04T09:00:00Z",
            "event_origin": {"location": "KRAKEN", "external_id": "acq-ext"},
            "account_chain_id": KRAKEN_ACCOUNT_ID,
            "asset_id": BTC,
            "is_fee": False,
            "kind": "ACQUISITION",
            "quantity_acquired": str(quantity_acquired),
            "cost_per_unit": str(cost_per_unit),
        }
    ]


def test_get_acquisition_disposal_returns_each_disposal_link_as_timeline_item(
    client: TestClient,
    persist_acquisition_disposal_projection: Callable[[AcquisitionDisposalProjection], None],
) -> None:
    first_lot = _acquisition_lot(
        external_id="first-acq-ext",
        timestamp=datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc),
        quantity_acquired=Decimal("0.5"),
        cost_per_unit=Decimal("10000"),
    )
    second_lot = _acquisition_lot(
        external_id="second-acq-ext",
        timestamp=datetime(2024, 1, 2, 9, 0, 0, tzinfo=timezone.utc),
        quantity_acquired=Decimal("0.5"),
        cost_per_unit=Decimal("20000"),
    )
    disposal_timestamp = datetime(2024, 1, 3, 9, 0, 0, tzinfo=timezone.utc)
    first_link = _disposal_link(
        lot=first_lot,
        external_id="disposal-ext",
        timestamp=disposal_timestamp,
        quantity_used=Decimal("0.25"),
        proceeds_total=Decimal("7500"),
    )
    second_link = _disposal_link(
        lot=second_lot,
        external_id="disposal-ext",
        timestamp=disposal_timestamp,
        quantity_used=Decimal("0.1"),
        proceeds_total=Decimal("3000"),
    )
    persist_acquisition_disposal_projection(
        AcquisitionDisposalProjection(
            acquisition_lots=[first_lot, second_lot],
            disposal_links=[first_link, second_link],
        )
    )

    response = client.get("/acquisition-disposal")
    response_items_by_id = {item["id"]: item for item in response.json()}
    first_disposal_item = response_items_by_id[str(first_link.id)]
    second_disposal_item = response_items_by_id[str(second_link.id)]
    expected_first_basis = first_link.quantity_used * first_lot.cost_per_unit
    expected_second_basis = second_link.quantity_used * second_lot.cost_per_unit

    assert response.status_code == 200
    assert first_disposal_item == {
        "id": str(first_link.id),
        "timestamp": "2024-01-03T09:00:00Z",
        "event_origin": {"location": "KRAKEN", "external_id": "disposal-ext"},
        "account_chain_id": KRAKEN_ACCOUNT_ID,
        "asset_id": BTC,
        "is_fee": False,
        "kind": "DISPOSAL",
        "acquisition_id": str(first_lot.id),
        "acquisition_timestamp": "2024-01-01T09:00:00Z",
        "acquisition_event_origin": {"location": "KRAKEN", "external_id": "first-acq-ext"},
        "quantity_used": str(first_link.quantity_used),
        "proceeds_total": str(first_link.proceeds_total),
        "cost_basis_total": str(expected_first_basis),
    }
    assert second_disposal_item == {
        "id": str(second_link.id),
        "timestamp": "2024-01-03T09:00:00Z",
        "event_origin": {"location": "KRAKEN", "external_id": "disposal-ext"},
        "account_chain_id": KRAKEN_ACCOUNT_ID,
        "asset_id": BTC,
        "is_fee": False,
        "kind": "DISPOSAL",
        "acquisition_id": str(second_lot.id),
        "acquisition_timestamp": "2024-01-02T09:00:00Z",
        "acquisition_event_origin": {"location": "KRAKEN", "external_id": "second-acq-ext"},
        "quantity_used": str(second_link.quantity_used),
        "proceeds_total": str(second_link.proceeds_total),
        "cost_basis_total": str(expected_second_basis),
    }
