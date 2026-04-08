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

    EUR_ASSET_ID = AssetId("EUR")

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
            projected_event = project_event_quantities(event, eur_asset_id=self.EUR_ASSET_ID)
            valued_event = value_projected_event(
                projected_event,
                eur_asset_id=self.EUR_ASSET_ID,
                price_provider=self._price_provider,
            )
            match_event_fifo(
                valued_event,
                open_lots_by_asset=open_lots_by_asset,
                acquisitions=acquisitions,
                disposals=disposals,
            )

        return AcquisitionDisposalProjection(
            acquisition_lots=acquisitions,
            disposal_links=disposals,
        )
