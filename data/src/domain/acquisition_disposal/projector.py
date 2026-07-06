from collections import defaultdict, deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal

from ..ledger import AssetId, EventOrigin, LedgerEvent
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
        self._acquisitions: list[AcquisitionLot] = []
        self._disposals: list[DisposalLink] = []
        self._open_lots_by_asset: dict[AssetId, deque[_LotBalance]] = defaultdict(deque)

    def projection(self) -> AcquisitionDisposalProjection:
        return AcquisitionDisposalProjection(
            acquisition_lots=list(self._acquisitions),
            disposal_links=list(self._disposals),
        )

    def project(
        self,
        events: Iterable[LedgerEvent],
        *,
        overrides_by_event_origin: Mapping[EventOrigin, Mapping[AssetId, Decimal]],
    ) -> AcquisitionDisposalProjection:
        """Events must be provided in chronological order."""
        for event in events:
            projected_event = project_event_quantities(event)
            try:
                prices = value_projected_event(
                    projected_event,
                    timestamp=event.timestamp,
                    price_provider=self._price_provider,
                    overrides=overrides_by_event_origin.get(event.event_origin, {}),
                )
            except AcquisitionDisposalProjectionError as error:
                _add_event_context(error, event=event)
                raise
            match_event_fifo(
                projected_event,
                prices=prices,
                event_origin=event.event_origin,
                timestamp=event.timestamp,
                open_lots_by_asset=self._open_lots_by_asset,
                acquisitions=self._acquisitions,
                disposals=self._disposals,
            )

        return self.projection()


def _add_event_context(
    error: AcquisitionDisposalProjectionError,
    *,
    event: LedgerEvent,
) -> None:
    origin = event.event_origin
    error.args = (f"{error} event_origin={origin.location.value}/{origin.external_id} @{event.timestamp.isoformat()}",)
    error.event = event
