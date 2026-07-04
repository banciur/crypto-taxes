from collections import deque
from decimal import Decimal
from uuid import uuid4

import pytest

from accounts import KRAKEN_ACCOUNT_ID
from domain.acquisition_disposal import AcquisitionDisposalProjectionError, AcquisitionLot, DisposalLink
from domain.acquisition_disposal.fifo import match_event_fifo
from domain.acquisition_disposal.pipeline_types import (
    _LotBalance,
    _ProjectedAssetResidualGroup,
    _ProjectedEvent,
    _ProjectedResidualLeg,
)
from domain.ledger import AssetId, EventLocation, EventOrigin
from tests.constants import BASE_WALLET, BTC, EUR, USD
from tests.domain.acquisition_disposal.helpers import BASE_TIMESTAMP, EXOTIC

EVENT_ORIGIN = EventOrigin(location=EventLocation.INTERNAL, external_id=str(uuid4()))


def _open_lot(*, asset_id: AssetId, quantity: str, cost_per_unit: str) -> _LotBalance:
    lot = AcquisitionLot(
        event_origin=EventOrigin(location=EventLocation.KRAKEN, external_id=str(uuid4())),
        account_chain_id=KRAKEN_ACCOUNT_ID,
        asset_id=asset_id,
        is_fee=False,
        timestamp=BASE_TIMESTAMP,
        quantity_acquired=Decimal(quantity),
        cost_per_unit=Decimal(cost_per_unit),
    )
    return _LotBalance(lot=lot, remaining_quantity=Decimal(quantity))


def test_single_acquisition() -> None:
    quantity = Decimal("0.5")
    cost = Decimal("40000")
    projected_event = _ProjectedEvent(
        non_fee_groups=[
            _ProjectedAssetResidualGroup(
                asset_id=BTC,
                residuals=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=quantity)],
            ),
        ],
        fee_groups=[],
    )
    acquisitions: list[AcquisitionLot] = []
    disposals: list[DisposalLink] = []

    match_event_fifo(
        projected_event,
        prices={BTC: cost},
        event_origin=EVENT_ORIGIN,
        timestamp=BASE_TIMESTAMP,
        open_lots_by_asset={},
        acquisitions=acquisitions,
        disposals=disposals,
    )

    assert disposals == []
    assert len(acquisitions) == 1

    new_lot = acquisitions[0]
    assert new_lot.quantity_acquired == quantity
    assert new_lot.asset_id == BTC
    assert new_lot.cost_per_unit == cost


def test_multiple_acquisitions() -> None:
    first_quantity = Decimal("0.5")
    second_quantity = Decimal("0.3")
    first_cost = Decimal("40000")
    second_cost = Decimal("45000")
    first_event = _ProjectedEvent(
        non_fee_groups=[
            _ProjectedAssetResidualGroup(
                asset_id=BTC,
                residuals=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=first_quantity)],
            ),
        ],
        fee_groups=[],
    )
    second_event = _ProjectedEvent(
        non_fee_groups=[
            _ProjectedAssetResidualGroup(
                asset_id=BTC,
                residuals=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=second_quantity)],
            ),
        ],
        fee_groups=[],
    )
    open_lots_by_asset: dict[AssetId, deque[_LotBalance]] = {}
    acquisitions: list[AcquisitionLot] = []
    disposals: list[DisposalLink] = []

    match_event_fifo(
        first_event,
        prices={BTC: first_cost},
        event_origin=EVENT_ORIGIN,
        timestamp=BASE_TIMESTAMP,
        open_lots_by_asset=open_lots_by_asset,
        acquisitions=acquisitions,
        disposals=disposals,
    )
    match_event_fifo(
        second_event,
        prices={BTC: second_cost},
        event_origin=EVENT_ORIGIN,
        timestamp=BASE_TIMESTAMP,
        open_lots_by_asset=open_lots_by_asset,
        acquisitions=acquisitions,
        disposals=disposals,
    )

    assert disposals == []
    assert [(lot.quantity_acquired, lot.cost_per_unit) for lot in acquisitions] == [
        (first_quantity, first_cost),
        (second_quantity, second_cost),
    ]


def test_single_disposal() -> None:
    acquired_quantity = Decimal("0.5")
    disposed_quantity = Decimal("0.2")
    acquisition_price = Decimal("40000")
    disposal_price = Decimal("45000")
    acquisition_event = _ProjectedEvent(
        non_fee_groups=[
            _ProjectedAssetResidualGroup(
                asset_id=BTC,
                residuals=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=acquired_quantity)],
            ),
        ],
        fee_groups=[],
    )
    disposal_event = _ProjectedEvent(
        non_fee_groups=[
            _ProjectedAssetResidualGroup(
                asset_id=BTC,
                residuals=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=-disposed_quantity)],
            ),
        ],
        fee_groups=[],
    )
    open_lots_by_asset: dict[AssetId, deque[_LotBalance]] = {}
    acquisitions: list[AcquisitionLot] = []
    disposals: list[DisposalLink] = []

    match_event_fifo(
        acquisition_event,
        prices={BTC: acquisition_price},
        event_origin=EVENT_ORIGIN,
        timestamp=BASE_TIMESTAMP,
        open_lots_by_asset=open_lots_by_asset,
        acquisitions=acquisitions,
        disposals=disposals,
    )
    match_event_fifo(
        disposal_event,
        prices={BTC: disposal_price},
        event_origin=EVENT_ORIGIN,
        timestamp=BASE_TIMESTAMP,
        open_lots_by_asset=open_lots_by_asset,
        acquisitions=acquisitions,
        disposals=disposals,
    )

    (acquisition_lot,) = acquisitions
    (disposal_link,) = disposals

    assert disposal_link.lot_id == acquisition_lot.id
    assert disposal_link.quantity_used == disposed_quantity
    assert disposal_link.proceeds_total == disposed_quantity * disposal_price


def test_multiple_disposals() -> None:
    acquired_quantity = Decimal("0.5")
    first_disposed_quantity = Decimal("0.2")
    second_disposed_quantity = Decimal("0.1")
    acquisition_price = Decimal("40000")
    first_disposal_price = Decimal("45000")
    second_disposal_price = Decimal("42000")
    acquisition_event = _ProjectedEvent(
        non_fee_groups=[
            _ProjectedAssetResidualGroup(
                asset_id=BTC,
                residuals=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=acquired_quantity)],
            ),
        ],
        fee_groups=[],
    )
    first_disposal_event = _ProjectedEvent(
        non_fee_groups=[
            _ProjectedAssetResidualGroup(
                asset_id=BTC,
                residuals=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=-first_disposed_quantity)],
            ),
        ],
        fee_groups=[],
    )
    second_disposal_event = _ProjectedEvent(
        non_fee_groups=[
            _ProjectedAssetResidualGroup(
                asset_id=BTC,
                residuals=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=-second_disposed_quantity)],
            ),
        ],
        fee_groups=[],
    )
    open_lots_by_asset: dict[AssetId, deque[_LotBalance]] = {}
    acquisitions: list[AcquisitionLot] = []
    disposals: list[DisposalLink] = []

    match_event_fifo(
        acquisition_event,
        prices={BTC: acquisition_price},
        event_origin=EVENT_ORIGIN,
        timestamp=BASE_TIMESTAMP,
        open_lots_by_asset=open_lots_by_asset,
        acquisitions=acquisitions,
        disposals=disposals,
    )
    match_event_fifo(
        first_disposal_event,
        prices={BTC: first_disposal_price},
        event_origin=EVENT_ORIGIN,
        timestamp=BASE_TIMESTAMP,
        open_lots_by_asset=open_lots_by_asset,
        acquisitions=acquisitions,
        disposals=disposals,
    )
    match_event_fifo(
        second_disposal_event,
        prices={BTC: second_disposal_price},
        event_origin=EVENT_ORIGIN,
        timestamp=BASE_TIMESTAMP,
        open_lots_by_asset=open_lots_by_asset,
        acquisitions=acquisitions,
        disposals=disposals,
    )

    (acquisition_lot,) = acquisitions

    assert [(link.lot_id, link.quantity_used, link.proceeds_total) for link in disposals] == [
        (acquisition_lot.id, first_disposed_quantity, first_disposed_quantity * first_disposal_price),
        (acquisition_lot.id, second_disposed_quantity, second_disposed_quantity * second_disposal_price),
    ]


def test_disposal_that_disposes_multiple_acquisitions() -> None:
    first_quantity = Decimal("0.5")
    second_quantity = Decimal("0.3")
    disposed_quantity = Decimal("0.7")
    first_price = Decimal("20000")
    second_price = Decimal("30000")
    disposal_price = Decimal("40000")
    first_acquisition_event = _ProjectedEvent(
        non_fee_groups=[
            _ProjectedAssetResidualGroup(
                asset_id=BTC,
                residuals=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=first_quantity)],
            ),
        ],
        fee_groups=[],
    )
    second_acquisition_event = _ProjectedEvent(
        non_fee_groups=[
            _ProjectedAssetResidualGroup(
                asset_id=BTC,
                residuals=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=second_quantity)],
            ),
        ],
        fee_groups=[],
    )
    disposal_event = _ProjectedEvent(
        non_fee_groups=[
            _ProjectedAssetResidualGroup(
                asset_id=BTC,
                residuals=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=-disposed_quantity)],
            ),
        ],
        fee_groups=[],
    )
    open_lots_by_asset: dict[AssetId, deque[_LotBalance]] = {}
    acquisitions: list[AcquisitionLot] = []
    disposals: list[DisposalLink] = []

    match_event_fifo(
        first_acquisition_event,
        prices={BTC: first_price},
        event_origin=EVENT_ORIGIN,
        timestamp=BASE_TIMESTAMP,
        open_lots_by_asset=open_lots_by_asset,
        acquisitions=acquisitions,
        disposals=disposals,
    )
    match_event_fifo(
        second_acquisition_event,
        prices={BTC: second_price},
        event_origin=EVENT_ORIGIN,
        timestamp=BASE_TIMESTAMP,
        open_lots_by_asset=open_lots_by_asset,
        acquisitions=acquisitions,
        disposals=disposals,
    )
    match_event_fifo(
        disposal_event,
        prices={BTC: disposal_price},
        event_origin=EVENT_ORIGIN,
        timestamp=BASE_TIMESTAMP,
        open_lots_by_asset=open_lots_by_asset,
        acquisitions=acquisitions,
        disposals=disposals,
    )

    first_lot, second_lot = acquisitions

    assert [(link.lot_id, link.quantity_used, link.proceeds_total) for link in disposals] == [
        (first_lot.id, first_quantity, first_quantity * disposal_price),
        (second_lot.id, disposed_quantity - first_quantity, (disposed_quantity - first_quantity) * disposal_price),
    ]


def test_raises_when_open_lots_are_insufficient() -> None:
    projected_event = _ProjectedEvent(
        non_fee_groups=[
            _ProjectedAssetResidualGroup(
                asset_id=BTC,
                residuals=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=Decimal("-1"))],
            ),
        ],
        fee_groups=[],
    )

    with pytest.raises(AcquisitionDisposalProjectionError, match="Not enough open lots") as exc_info:
        match_event_fifo(
            projected_event,
            prices={BTC: Decimal("40000")},
            event_origin=EVENT_ORIGIN,
            timestamp=BASE_TIMESTAMP,
            open_lots_by_asset={},
            acquisitions=[],
            disposals=[],
        )

    assert exc_info.value.quantity_needed == Decimal("1")


def test_skips_fiat_groups() -> None:
    btc_quantity = Decimal("0.5")
    btc_price = Decimal("40000")
    projected_event = _ProjectedEvent(
        non_fee_groups=[
            _ProjectedAssetResidualGroup(
                asset_id=BTC,
                residuals=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=btc_quantity)],
            ),
            _ProjectedAssetResidualGroup(
                asset_id=EUR,
                residuals=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=Decimal("100"))],
            ),
            _ProjectedAssetResidualGroup(
                asset_id=USD,
                residuals=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=Decimal("-50"))],
            ),
        ],
        fee_groups=[],
    )
    acquisitions: list[AcquisitionLot] = []
    disposals: list[DisposalLink] = []

    match_event_fifo(
        projected_event,
        prices={BTC: btc_price, EUR: Decimal("1"), USD: Decimal("0.9")},
        event_origin=EVENT_ORIGIN,
        timestamp=BASE_TIMESTAMP,
        open_lots_by_asset={},
        acquisitions=acquisitions,
        disposals=disposals,
    )

    assert len(acquisitions) == 1
    assert disposals == []

    (new_lot,) = acquisitions
    assert new_lot.asset_id == BTC
    assert new_lot.quantity_acquired == btc_quantity
    assert new_lot.cost_per_unit == btc_price


def test_processes_disposals_before_same_event_acquisitions() -> None:
    existing_lot = _open_lot(asset_id=EXOTIC, quantity="5", cost_per_unit="10")
    projected_event = _ProjectedEvent(
        non_fee_groups=[
            _ProjectedAssetResidualGroup(
                asset_id=EXOTIC,
                residuals=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=Decimal("100"))],
            ),
        ],
        fee_groups=[
            _ProjectedAssetResidualGroup(
                asset_id=EXOTIC,
                residuals=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=Decimal("-1"))],
            ),
        ],
    )
    acquisitions: list[AcquisitionLot] = []
    disposals: list[DisposalLink] = []

    match_event_fifo(
        projected_event,
        prices={EXOTIC: Decimal("11")},
        event_origin=EVENT_ORIGIN,
        timestamp=BASE_TIMESTAMP,
        open_lots_by_asset={EXOTIC: deque([existing_lot])},
        acquisitions=acquisitions,
        disposals=disposals,
    )

    (fee_link,) = disposals
    (new_lot,) = acquisitions

    assert fee_link.lot_id == existing_lot.lot.id
    assert fee_link.quantity_used == Decimal("1")
    assert fee_link.is_fee is True
    assert new_lot.quantity_acquired == Decimal("100")


def test_does_not_allow_fee_disposal_to_consume_same_event_non_fee_acquisition() -> None:
    projected_event = _ProjectedEvent(
        non_fee_groups=[
            _ProjectedAssetResidualGroup(
                asset_id=EXOTIC,
                residuals=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=Decimal("100"))],
            ),
        ],
        fee_groups=[
            _ProjectedAssetResidualGroup(
                asset_id=EXOTIC,
                residuals=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=Decimal("-1"))],
            ),
        ],
    )

    with pytest.raises(AcquisitionDisposalProjectionError, match="Not enough open lots") as exc_info:
        match_event_fifo(
            projected_event,
            prices={EXOTIC: Decimal("11")},
            event_origin=EVENT_ORIGIN,
            timestamp=BASE_TIMESTAMP,
            open_lots_by_asset={},
            acquisitions=[],
            disposals=[],
        )

    assert exc_info.value.quantity_needed == Decimal("1")
