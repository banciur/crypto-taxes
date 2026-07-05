from datetime import datetime
from decimal import Decimal

import pytest

from domain.acquisition_disposal.errors import (
    AcquisitionDisposalProjectionError,
    AcquisitionDisposalValuationError,
    RequiredValuationPriceUnavailableError,
)
from domain.acquisition_disposal.projector import AcquisitionDisposalProjector
from domain.ledger import AssetId
from domain.pricing import PriceProvider, RequiredPriceUnavailableError
from tests.constants import EUR, USDC
from tests.domain.acquisition_disposal.helpers import BASE_TIMESTAMP, make_event
from tests.helpers.ledger import make_leg

LP = AssetId("LP")


class EmptyPriceProvider(PriceProvider):
    def rate(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> Decimal:
        _ = base_id, quote_id, timestamp
        raise LookupError("Missing price")


class RequiredPriceProvider(PriceProvider):
    def rate(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> Decimal:
        raise RequiredPriceUnavailableError(
            base_id=base_id,
            quote_id=quote_id,
            timestamp=timestamp,
            reason="Required price missing",
        )


def test_valuation_error_includes_event_context() -> None:
    external_id = "projector-unpriced"
    event = make_event(
        external_id=external_id,
        legs=[make_leg(asset_id=LP, quantity=Decimal("1"))],
        timestamp=BASE_TIMESTAMP,
    )

    with pytest.raises(AcquisitionDisposalProjectionError) as exc_info:
        AcquisitionDisposalProjector(price_provider=EmptyPriceProvider()).project([event])

    message = str(exc_info.value)
    assert f"asset={LP}" in message
    assert f"event_origin={event.event_origin.location.value}/{external_id}" in message
    assert f"@{BASE_TIMESTAMP.isoformat()}" in message
    assert exc_info.value.event == event
    assert isinstance(exc_info.value, AcquisitionDisposalValuationError)
    assert EUR not in message


def test_required_price_error_includes_event_context() -> None:
    external_id = "projector-required-price"
    event = make_event(
        external_id=external_id,
        legs=[make_leg(asset_id=USDC, quantity=Decimal("1"))],
        timestamp=BASE_TIMESTAMP,
    )

    with pytest.raises(AcquisitionDisposalProjectionError) as exc_info:
        AcquisitionDisposalProjector(price_provider=RequiredPriceProvider()).project([event])

    message = str(exc_info.value)
    assert f"base={USDC}" in message
    assert f"quote={EUR}" in message
    assert f"event_origin={event.event_origin.location.value}/{external_id}" in message
    assert f"@{BASE_TIMESTAMP.isoformat()}" in message
    assert exc_info.value.event == event
    assert isinstance(exc_info.value, RequiredValuationPriceUnavailableError)
    assert exc_info.value.pricing_error.base_id == USDC
    assert exc_info.value.pricing_error.quote_id == EUR
    assert exc_info.value.pricing_error.timestamp == BASE_TIMESTAMP
