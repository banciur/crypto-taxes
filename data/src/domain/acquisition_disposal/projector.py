from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable

from ..ledger import AssetId, LedgerEvent
from ..pricing import PriceProvider
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
    """Project ledger events into acquisition lots and disposal links."""

    def __init__(
        self,
        *,
        price_provider: PriceProvider,
    ) -> None:
        self._price_provider = price_provider

    def project(self, events: Iterable[LedgerEvent]) -> AcquisitionDisposalProjection:
        """Caller must provide events in chronological order."""
        acquisitions: list[AcquisitionLot] = []
        disposals: list[DisposalLink] = []
        open_lots_by_asset: dict[AssetId, deque[_LotBalance]] = defaultdict(deque)

        for event in events:
            projected_event = project_event_quantities(event)
            prices = value_projected_event(
                projected_event,
                timestamp=event.timestamp,
                price_provider=self._price_provider,
            )
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
