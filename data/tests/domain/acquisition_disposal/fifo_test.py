from __future__ import annotations

from collections import deque
from decimal import Decimal
from uuid import uuid4

import pytest

from accounts import KRAKEN_ACCOUNT_ID
from domain.acquisition_disposal import AcquisitionDisposalProjectionError, AcquisitionLot, DisposalLink
from domain.acquisition_disposal.fifo import match_event_fifo
from domain.acquisition_disposal.pipeline_types import (
    _LotBalance,
    _ProjectedAssetGroup,
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


def test_fifo_splits_one_projected_disposal_leg_across_multiple_open_lots() -> None:
    first_lot = _open_lot(asset_id=BTC, quantity="0.5", cost_per_unit="20000")
    second_lot = _open_lot(asset_id=BTC, quantity="0.3", cost_per_unit="30000")
    projected_event = _ProjectedEvent(
        non_fee_groups=[
            _ProjectedAssetGroup(
                asset_id=BTC,
                is_fee=False,
                legs=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=Decimal("-0.7"))],
            ),
        ],
        fee_groups=[],
    )
    open_lots_by_asset = {BTC: deque([first_lot, second_lot])}
    acquisitions: list[AcquisitionLot] = []
    disposals: list[DisposalLink] = []

    match_event_fifo(
        projected_event,
        prices={BTC: Decimal("40000")},
        event_origin=EVENT_ORIGIN,
        timestamp=BASE_TIMESTAMP,
        open_lots_by_asset=open_lots_by_asset,
        acquisitions=acquisitions,
        disposals=disposals,
    )

    assert acquisitions == []
    assert [(link.lot_id, link.quantity_used, link.proceeds_total) for link in disposals] == [
        (first_lot.lot.id, Decimal("0.5"), Decimal("20000")),
        (second_lot.lot.id, Decimal("0.2"), Decimal("8000.0")),
    ]


def test_fifo_processes_disposals_before_same_event_acquisitions() -> None:
    existing_lot = _open_lot(asset_id=EXOTIC, quantity="5", cost_per_unit="10")
    projected_event = _ProjectedEvent(
        non_fee_groups=[
            _ProjectedAssetGroup(
                asset_id=EXOTIC,
                is_fee=False,
                legs=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=Decimal("100"))],
            ),
        ],
        fee_groups=[
            _ProjectedAssetGroup(
                asset_id=EXOTIC,
                is_fee=True,
                legs=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=Decimal("-1"))],
            ),
        ],
    )
    open_lots_by_asset = {EXOTIC: deque([existing_lot])}
    acquisitions: list[AcquisitionLot] = []
    disposals: list[DisposalLink] = []

    match_event_fifo(
        projected_event,
        prices={EXOTIC: Decimal("11")},
        event_origin=EVENT_ORIGIN,
        timestamp=BASE_TIMESTAMP,
        open_lots_by_asset=open_lots_by_asset,
        acquisitions=acquisitions,
        disposals=disposals,
    )

    (fee_link,) = disposals
    (new_lot,) = acquisitions

    assert fee_link.lot_id == existing_lot.lot.id
    assert fee_link.quantity_used == Decimal("1")
    assert fee_link.is_fee is True
    assert new_lot.quantity_acquired == Decimal("100")
    assert list(open_lots_by_asset[EXOTIC]) == [
        _LotBalance(lot=existing_lot.lot, remaining_quantity=Decimal("4")),
        _LotBalance(lot=new_lot, remaining_quantity=Decimal("100")),
    ]


def test_fifo_raises_when_open_lots_are_insufficient() -> None:
    projected_event = _ProjectedEvent(
        non_fee_groups=[
            _ProjectedAssetGroup(
                asset_id=BTC,
                is_fee=False,
                legs=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=Decimal("-1"))],
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


def test_fifo_skips_fiat_groups() -> None:
    projected_event = _ProjectedEvent(
        non_fee_groups=[
            _ProjectedAssetGroup(
                asset_id=EUR,
                is_fee=False,
                legs=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=Decimal("100"))],
            ),
            _ProjectedAssetGroup(
                asset_id=USD,
                is_fee=False,
                legs=[_ProjectedResidualLeg(account_chain_id=BASE_WALLET, quantity=Decimal("-50"))],
            ),
        ],
        fee_groups=[],
    )
    acquisitions: list[AcquisitionLot] = []
    disposals: list[DisposalLink] = []

    match_event_fifo(
        projected_event,
        prices={EUR: Decimal("1"), USD: Decimal("0.9")},
        event_origin=EVENT_ORIGIN,
        timestamp=BASE_TIMESTAMP,
        open_lots_by_asset={},
        acquisitions=acquisitions,
        disposals=disposals,
    )

    assert acquisitions == []
    assert disposals == []
