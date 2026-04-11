from __future__ import annotations

from accounts import KRAKEN_ACCOUNT_ID
from domain.acquisition_disposal.models import AbstractAcquisitionDisposal
from domain.ledger import EventLegRef, EventLocation, EventOrigin, LegKey
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
