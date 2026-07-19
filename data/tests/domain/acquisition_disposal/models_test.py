from decimal import Decimal
from uuid import uuid4

from accounts import KRAKEN_ACCOUNT_ID
from domain.acquisition_disposal.models import AbstractAcquisitionDisposal, AcquisitionLot, DisposalLink
from domain.ledger import EventLegRef, EventLocation, EventOrigin, LegKey, LotId
from tests.constants import BTC
from tests.domain.acquisition_disposal.helpers import BASE_TIMESTAMP


class _TestAcquisitionDisposal(AbstractAcquisitionDisposal):
    pass


def test_abstract_acquisition_disposal_derives_leg_identity() -> None:
    event_origin = EventOrigin(location=EventLocation.KRAKEN, external_id="identity")

    projection = _TestAcquisitionDisposal(
        event_origin=event_origin,
        account_chain_id=KRAKEN_ACCOUNT_ID,
        asset_id=BTC,
        is_fee=False,
        timestamp=BASE_TIMESTAMP,
    )

    assert projection.leg_key == LegKey(account_chain_id=KRAKEN_ACCOUNT_ID, asset_id=BTC, is_fee=False)
    assert projection.source_leg_ref == EventLegRef(event_origin=event_origin, leg_key=projection.leg_key)


def test_acquisition_lot_accepts_negative_cost_basis() -> None:
    lot = AcquisitionLot(
        event_origin=EventOrigin(location=EventLocation.KRAKEN, external_id="liability"),
        account_chain_id=KRAKEN_ACCOUNT_ID,
        asset_id=BTC,
        is_fee=False,
        timestamp=BASE_TIMESTAMP,
        quantity_acquired=Decimal("1"),
        cost_per_unit=Decimal("-2500"),
    )

    assert lot.cost_per_unit == Decimal("-2500")


def test_disposal_link_accepts_negative_proceeds() -> None:
    link = DisposalLink(
        event_origin=EventOrigin(location=EventLocation.KRAKEN, external_id="liability"),
        account_chain_id=KRAKEN_ACCOUNT_ID,
        asset_id=BTC,
        is_fee=False,
        timestamp=BASE_TIMESTAMP,
        lot_id=LotId(uuid4()),
        quantity_used=Decimal("1"),
        proceeds_total=Decimal("-2500"),
    )

    assert link.proceeds_total == Decimal("-2500")
