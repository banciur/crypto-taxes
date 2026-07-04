from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable

from ..ledger import AssetId, LedgerEvent
from ..pricing import PriceProvider
from .errors import AcquisitionDisposalProjectionError
from .fifo import match_event_fifo
from .models import AcquisitionLot, DisposalLink
from .pipeline_types import _LotBalance
from .quantities import project_event_quantities
from .valuation import value_projected_event


@dataclass(frozen=True)
class AcquisitionDisposalProjection:
    acquisition_lots: list[AcquisitionLot]
    disposal_links: list[DisposalLink]


class AcquisitionDisposalProjector:
    def __init__(
        self,
        *,
        price_provider: PriceProvider,
    ) -> None:
        self._price_provider = price_provider

    def project(self, events: Iterable[LedgerEvent]) -> AcquisitionDisposalProjection:
        """Events must be provided in chronological order."""
        acquisitions: list[AcquisitionLot] = []
        disposals: list[DisposalLink] = []
        open_lots_by_asset: dict[AssetId, deque[_LotBalance]] = defaultdict(deque)

        for event in events:
            projected_event = project_event_quantities(event)
            try:
                prices = value_projected_event(
                    projected_event,
                    timestamp=event.timestamp,
                    price_provider=self._price_provider,
                )
            except AcquisitionDisposalProjectionError as error:
                _add_event_context(error, event=event)
                raise
            match_event_fifo(
                projected_event,
                prices=prices,
                event_origin=event.event_origin,
                timestamp=event.timestamp,
                open_lots_by_asset=open_lots_by_asset,
                acquisitions=acquisitions,
                disposals=disposals,
            )

        return AcquisitionDisposalProjection(
            acquisition_lots=acquisitions,
            disposal_links=disposals,
        )


def _add_event_context(
    error: AcquisitionDisposalProjectionError,
    *,
    event: LedgerEvent,
) -> None:
    origin = event.event_origin
    error.args = (f"{error} event_origin={origin.location.value}/{origin.external_id} @{event.timestamp.isoformat()}",)
    error.event = event
