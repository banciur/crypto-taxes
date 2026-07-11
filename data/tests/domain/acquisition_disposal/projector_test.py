from datetime import datetime
from decimal import Decimal

import pytest

from domain.acquisition_disposal.errors import (
    AcquisitionDisposalProjectionError,
    AcquisitionDisposalValuationError,
)
from domain.acquisition_disposal.projector import AcquisitionDisposalProjector
from domain.ledger import AssetId
from domain.pricing import PriceProvider
from tests.constants import EUR, USDC
from tests.domain.acquisition_disposal.helpers import BASE_TIMESTAMP, make_event
from tests.helpers.ledger import make_leg

LP = AssetId("LP")


class EmptyPriceProvider(PriceProvider):
    def rate(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> Decimal | None:
        _ = base_id, quote_id, timestamp
        return None


def test_valuation_error_includes_event_context() -> None:
    external_id = "projector-unpriced"
    event = make_event(
        external_id=external_id,
        legs=[make_leg(asset_id=LP, quantity=Decimal("1"))],
        timestamp=BASE_TIMESTAMP,
    )

    with pytest.raises(AcquisitionDisposalProjectionError) as exc_info:
        AcquisitionDisposalProjector(price_provider=EmptyPriceProvider()).project([event], overrides_by_event_origin={})

    message = str(exc_info.value)
    assert f"asset={LP}" in message
    assert f"event_origin={event.event_origin}" in message
    assert f"@{BASE_TIMESTAMP.isoformat()}" in message
    assert exc_info.value.event == event
    assert isinstance(exc_info.value, AcquisitionDisposalValuationError)
    assert EUR not in message


def test_override_prices_otherwise_unpriceable_acquisition() -> None:
    event = make_event(
        legs=[make_leg(asset_id=LP, quantity=Decimal("2"))],
        timestamp=BASE_TIMESTAMP,
    )
    overrides_by_event_origin = {event.event_origin: {LP: Decimal("1500")}}

    projection = AcquisitionDisposalProjector(price_provider=EmptyPriceProvider()).project(
        [event],
        overrides_by_event_origin=overrides_by_event_origin,
    )

    assert len(projection.acquisition_lots) == 1
    lot = projection.acquisition_lots[0]
    assert lot.asset_id == LP
    assert lot.quantity_acquired == Decimal("2")
    assert lot.cost_per_unit == Decimal("1500")


def test_unpriceable_anchor_error_includes_event_context() -> None:
    external_id = "projector-unpriceable-anchor"
    event = make_event(
        external_id=external_id,
        legs=[make_leg(asset_id=USDC, quantity=Decimal("1"))],
        timestamp=BASE_TIMESTAMP,
    )

    with pytest.raises(AcquisitionDisposalProjectionError) as exc_info:
        AcquisitionDisposalProjector(price_provider=EmptyPriceProvider()).project([event], overrides_by_event_origin={})

    message = str(exc_info.value)
    assert "Valuation anchor asset" in message
    assert f"asset={USDC}" in message
    assert f"event_origin={event.event_origin}" in message
    assert f"@{BASE_TIMESTAMP.isoformat()}" in message
    assert exc_info.value.event == event
    assert isinstance(exc_info.value, AcquisitionDisposalValuationError)
