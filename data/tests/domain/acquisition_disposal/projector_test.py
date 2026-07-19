from datetime import datetime, timedelta
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
LP_A = AssetId("LP_A")
LP_B = AssetId("LP_B")
FEE_ASSET = AssetId("FEE_ASSET")


class EmptyPriceProvider(PriceProvider):
    def rate(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> Decimal | None:
        _ = base_id, quote_id, timestamp
        return None


class TimestampPriceProvider(PriceProvider):
    def __init__(self, rates: dict[tuple[AssetId, datetime], Decimal]) -> None:
        self._rates = rates

    def rate(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> Decimal | None:
        if base_id == quote_id:
            return Decimal(1)
        if quote_id != EUR:
            raise LookupError(f"Unsupported quote asset: {quote_id}")
        return self._rates.get((base_id, timestamp))


class FailingPriceProvider(PriceProvider):
    def rate(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> Decimal | None:
        _ = base_id, quote_id, timestamp
        raise RuntimeError("price backend failed")


def test_valuation_error_includes_event_context() -> None:
    external_id = "projector-unpriced"
    event = make_event(
        external_id=external_id,
        legs=[make_leg(asset_id=LP, quantity=Decimal("1"))],
        timestamp=BASE_TIMESTAMP,
    )

    with pytest.raises(AcquisitionDisposalProjectionError) as exc_info:
        AcquisitionDisposalProjector(
            price_provider=EmptyPriceProvider(),
            overrides_by_event_origin={},
        ).project(events=[event])

    message = str(exc_info.value)
    assert f"asset={LP}" in message
    assert f"event_origin={event.event_origin}" in message
    assert f"@{BASE_TIMESTAMP.isoformat()}" in message
    assert exc_info.value.event == event
    assert isinstance(exc_info.value, AcquisitionDisposalValuationError)
    assert EUR not in message


def test_override_prices_otherwise_unpriceable_acquisition() -> None:
    lp_quantity = Decimal("2")
    lp_override_rate = Decimal("1500")
    event = make_event(
        legs=[make_leg(asset_id=LP, quantity=lp_quantity)],
        timestamp=BASE_TIMESTAMP,
    )
    overrides_by_event_origin = {event.event_origin: {LP: lp_override_rate}}

    projection = AcquisitionDisposalProjector(
        price_provider=EmptyPriceProvider(),
        overrides_by_event_origin=overrides_by_event_origin,
    ).project(events=[event])

    assert len(projection.acquisition_lots) == 1
    lot = projection.acquisition_lots[0]
    assert lot.asset_id == LP
    assert lot.quantity_acquired == lp_quantity
    assert lot.cost_per_unit == lp_override_rate


def test_unpriceable_reference_asset_error_includes_event_context() -> None:
    external_id = "projector-unpriceable-reference"
    event = make_event(
        external_id=external_id,
        legs=[make_leg(asset_id=USDC, quantity=Decimal("1"))],
        timestamp=BASE_TIMESTAMP,
    )

    with pytest.raises(AcquisitionDisposalProjectionError) as exc_info:
        AcquisitionDisposalProjector(
            price_provider=EmptyPriceProvider(),
            overrides_by_event_origin={},
        ).project(events=[event])

    message = str(exc_info.value)
    assert "Reference-priced asset" in message
    assert f"asset={USDC}" in message
    assert f"event_origin={event.event_origin}" in message
    assert f"@{BASE_TIMESTAMP.isoformat()}" in message
    assert exc_info.value.event == event
    assert isinstance(exc_info.value, AcquisitionDisposalValuationError)


@pytest.mark.parametrize(
    ("past_offset", "future_offset", "expected_rate"),
    [
        (-2, 1, Decimal("20")),
        (-1, 3, Decimal("10")),
    ],
)
def test_one_sided_event_borrows_rate_from_closest_standard_anchor(
    past_offset: int,
    future_offset: int,
    expected_rate: Decimal,
) -> None:
    target_timestamp = BASE_TIMESTAMP
    past_timestamp = target_timestamp + timedelta(days=past_offset)
    future_timestamp = target_timestamp + timedelta(days=future_offset)
    past_rate = Decimal("10")
    future_rate = Decimal("20")
    quantity = Decimal("1")
    past = make_event(
        external_id="past-anchor",
        legs=[make_leg(asset_id=LP, quantity=quantity)],
        timestamp=past_timestamp,
    )
    target = make_event(
        external_id="target",
        legs=[make_leg(asset_id=LP, quantity=quantity)],
        timestamp=target_timestamp,
    )
    future = make_event(
        external_id="future-anchor",
        legs=[make_leg(asset_id=LP, quantity=quantity)],
        timestamp=future_timestamp,
    )
    projection = AcquisitionDisposalProjector(
        price_provider=TimestampPriceProvider(
            {
                (LP, past_timestamp): past_rate,
                (LP, future_timestamp): future_rate,
            }
        ),
        overrides_by_event_origin={},
    ).project(events=[past, target, future])

    target_lot = next(lot for lot in projection.acquisition_lots if lot.event_origin == target.event_origin)

    assert target_lot.cost_per_unit == expected_rate


def test_equal_distance_anchors_are_selected_by_event_origin() -> None:
    anchor_timestamp = BASE_TIMESTAMP
    target_timestamp = anchor_timestamp + timedelta(days=1)
    first_rate = Decimal("10")
    second_rate = Decimal("20")
    quantity = Decimal("1")
    second = make_event(
        external_id="z-anchor",
        legs=[make_leg(asset_id=LP, quantity=quantity)],
        timestamp=anchor_timestamp,
    )
    first = make_event(
        external_id="a-anchor",
        legs=[make_leg(asset_id=LP, quantity=quantity)],
        timestamp=anchor_timestamp,
    )
    target = make_event(
        external_id="target",
        legs=[make_leg(asset_id=LP, quantity=quantity)],
        timestamp=target_timestamp,
    )
    projection = AcquisitionDisposalProjector(
        price_provider=EmptyPriceProvider(),
        overrides_by_event_origin={
            first.event_origin: {LP: first_rate},
            second.event_origin: {LP: second_rate},
        },
    ).project(events=[second, first, target])

    target_lot = next(lot for lot in projection.acquisition_lots if lot.event_origin == target.event_origin)

    assert target_lot.cost_per_unit == first_rate


def test_two_missing_rates_borrow_one_and_remainder_solve_the_other() -> None:
    anchor_rate = Decimal("10")
    disposed_quantity = Decimal("2")
    acquired_quantity = Decimal("4")
    expected_acquired_rate = anchor_rate * disposed_quantity / acquired_quantity
    anchor = make_event(
        external_id="lp-a-anchor",
        legs=[make_leg(asset_id=LP_A, quantity=disposed_quantity)],
        offset_days=-1,
    )
    target = make_event(
        external_id="target",
        legs=[
            make_leg(asset_id=LP_A, quantity=-disposed_quantity),
            make_leg(asset_id=LP_B, quantity=acquired_quantity),
        ],
    )
    projection = AcquisitionDisposalProjector(
        price_provider=EmptyPriceProvider(),
        overrides_by_event_origin={anchor.event_origin: {LP_A: anchor_rate}},
    ).project(events=[anchor, target])

    target_lot = next(
        lot for lot in projection.acquisition_lots if lot.event_origin == target.event_origin and lot.asset_id == LP_B
    )

    assert target_lot.cost_per_unit == expected_acquired_rate


def test_one_sided_event_borrows_every_missing_rate() -> None:
    first_rate = Decimal("10")
    second_rate = Decimal("20")
    quantity = Decimal("1")
    first_anchor = make_event(
        external_id="lp-a-anchor",
        legs=[make_leg(asset_id=LP_A, quantity=quantity)],
        offset_days=-2,
    )
    second_anchor = make_event(
        external_id="lp-b-anchor",
        legs=[make_leg(asset_id=LP_B, quantity=quantity)],
        offset_days=-1,
    )
    target = make_event(
        external_id="target",
        legs=[
            make_leg(asset_id=LP_A, quantity=quantity),
            make_leg(asset_id=LP_B, quantity=quantity),
        ],
    )
    projection = AcquisitionDisposalProjector(
        price_provider=EmptyPriceProvider(),
        overrides_by_event_origin={
            first_anchor.event_origin: {LP_A: first_rate},
            second_anchor.event_origin: {LP_B: second_rate},
        },
    ).project(events=[first_anchor, second_anchor, target])

    target_rates = {
        lot.asset_id: lot.cost_per_unit
        for lot in projection.acquisition_lots
        if lot.event_origin == target.event_origin
    }

    assert target_rates == {LP_A: first_rate, LP_B: second_rate}


def test_standard_remainder_solved_rate_can_anchor_another_event() -> None:
    eur_quantity = Decimal("-100")
    anchor_quantity = Decimal("5")
    target_quantity = Decimal("1")
    expected_rate = abs(eur_quantity) / anchor_quantity
    anchor = make_event(
        external_id="remainder-anchor",
        legs=[
            make_leg(asset_id=EUR, quantity=eur_quantity),
            make_leg(asset_id=LP, quantity=anchor_quantity),
        ],
        offset_days=-1,
    )
    target = make_event(
        external_id="target",
        legs=[make_leg(asset_id=LP, quantity=target_quantity)],
    )
    projection = AcquisitionDisposalProjector(
        price_provider=TimestampPriceProvider({}),
        overrides_by_event_origin={},
    ).project(events=[anchor, target])

    target_lot = next(lot for lot in projection.acquisition_lots if lot.event_origin == target.event_origin)

    assert target_lot.cost_per_unit == expected_rate


def test_adjacent_resolved_event_does_not_become_an_anchor() -> None:
    anchor_rate = Decimal("10")
    quantity = Decimal("1")
    anchor = make_event(
        external_id="lp-a-anchor",
        legs=[make_leg(asset_id=LP_A, quantity=quantity)],
        offset_days=-2,
    )
    resolved_by_anchor = make_event(
        external_id="resolved-by-anchor",
        legs=[
            make_leg(asset_id=LP_A, quantity=-quantity),
            make_leg(asset_id=LP_B, quantity=quantity),
        ],
        offset_days=-1,
    )
    blocked = make_event(
        external_id="blocked",
        legs=[make_leg(asset_id=LP_B, quantity=quantity)],
    )
    projector = AcquisitionDisposalProjector(
        price_provider=EmptyPriceProvider(),
        overrides_by_event_origin={anchor.event_origin: {LP_A: anchor_rate}},
    )

    with pytest.raises(AcquisitionDisposalProjectionError) as exc_info:
        projector.project(events=[anchor, resolved_by_anchor, blocked])

    assert exc_info.value.event == blocked
    assert f"asset={LP_B}" in str(exc_info.value)
    assert projector.projection().acquisition_lots == []
    assert projector.projection().disposal_links == []


def test_same_anchor_event_uses_asset_id_to_choose_first_borrowed_rate() -> None:
    first_rate = Decimal("10")
    second_rate = Decimal("30")
    quantity = Decimal("1")
    anchor = make_event(
        external_id="anchor",
        legs=[
            make_leg(asset_id=LP_A, quantity=quantity),
            make_leg(asset_id=LP_B, quantity=quantity),
        ],
        offset_days=-1,
    )
    target = make_event(
        external_id="target",
        legs=[
            make_leg(asset_id=LP_A, quantity=-quantity),
            make_leg(asset_id=LP_B, quantity=quantity),
        ],
    )
    projection = AcquisitionDisposalProjector(
        price_provider=EmptyPriceProvider(),
        overrides_by_event_origin={anchor.event_origin: {LP_A: first_rate, LP_B: second_rate}},
    ).project(events=[anchor, target])

    target_lot = next(
        lot for lot in projection.acquisition_lots if lot.event_origin == target.event_origin and lot.asset_id == LP_B
    )

    assert target_lot.cost_per_unit == first_rate


def test_override_wins_when_price_provider_has_a_rate() -> None:
    provider_rate = Decimal("100")
    override_rate = Decimal("42")
    quantity = Decimal("1")
    event = make_event(
        external_id="override",
        legs=[make_leg(asset_id=LP, quantity=quantity)],
    )
    projection = AcquisitionDisposalProjector(
        price_provider=TimestampPriceProvider({(LP, event.timestamp): provider_rate}),
        overrides_by_event_origin={event.event_origin: {LP: override_rate}},
    ).project(events=[event])

    (lot,) = projection.acquisition_lots

    assert lot.cost_per_unit == override_rate


def test_missing_fee_rate_fails_with_event_context_before_fifo() -> None:
    lp_rate = Decimal("42")
    quantity = Decimal("1")
    event = make_event(
        external_id="missing-fee",
        legs=[
            make_leg(asset_id=LP, quantity=quantity),
            make_leg(asset_id=FEE_ASSET, quantity=-quantity, is_fee=True),
        ],
    )
    projector = AcquisitionDisposalProjector(
        price_provider=EmptyPriceProvider(),
        overrides_by_event_origin={event.event_origin: {LP: lp_rate}},
    )

    with pytest.raises(AcquisitionDisposalProjectionError, match="fee legs") as exc_info:
        projector.project(events=[event])

    assert exc_info.value.event == event
    assert projector.projection().acquisition_lots == []
    assert projector.projection().disposal_links == []


def test_price_provider_failure_is_not_treated_as_an_unavailable_rate() -> None:
    event = make_event(
        external_id="provider-failure",
        legs=[make_leg(asset_id=LP, quantity=Decimal("1"))],
    )

    with pytest.raises(RuntimeError, match="price backend failed"):
        AcquisitionDisposalProjector(
            price_provider=FailingPriceProvider(),
            overrides_by_event_origin={},
        ).project(events=[event])
