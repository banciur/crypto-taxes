from collections import defaultdict, deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from ..ledger import AssetId, EventOrigin, LedgerEvent
from ..pricing import PriceProvider
from .errors import AcquisitionDisposalProjectionError
from .fifo import match_event_fifo
from .models import AcquisitionLot, DisposalLink
from .pipeline_types import _LotBalance, _ProjectedEvent
from .quantities import project_event_quantities
from .valuation import _DirectRateResolver


@dataclass(frozen=True)
class AcquisitionDisposalProjection:
    acquisition_lots: list[AcquisitionLot]
    disposal_links: list[DisposalLink]


@dataclass(frozen=True)
class _ProjectedLedgerEvent:
    ledger_event: LedgerEvent
    projected_event: _ProjectedEvent


@dataclass(frozen=True)
class _StandardNonFeeValuation:
    resolved: dict[EventOrigin, dict[AssetId, Decimal]]
    unresolved: list[_ProjectedLedgerEvent]


@dataclass(frozen=True)
class _Anchor:
    event_origin: EventOrigin
    timestamp: datetime
    rate: Decimal


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
        *,
        events: Iterable[LedgerEvent],
        overrides_by_event_origin: Mapping[EventOrigin, Mapping[AssetId, Decimal]],
    ) -> AcquisitionDisposalProjection:
        """Events must be provided in chronological order."""
        projected_events = [
            _ProjectedLedgerEvent(
                ledger_event=event,
                projected_event=project_event_quantities(event),
            )
            for event in events
        ]
        rate_resolver = _DirectRateResolver(
            price_provider=self._price_provider,
            overrides_by_event_origin=overrides_by_event_origin,
        )

        standard_valuation = _value_standard_non_fee_events(
            projected_events=projected_events,
            rate_resolver=rate_resolver,
        )
        non_fee_rates_by_event_origin = dict(standard_valuation.resolved)

        if standard_valuation.unresolved:
            anchors = _index_anchors(
                projected_events=projected_events,
                rates_by_event_origin=standard_valuation.resolved,
            )
            non_fee_rates_by_event_origin.update(
                _resolve_non_fee_events_by_anchor(
                    unresolved_events=standard_valuation.unresolved,
                    anchors=anchors,
                    rate_resolver=rate_resolver,
                )
            )

        rates_by_event_origin = _complete_rates_with_fees(
            projected_events=projected_events,
            non_fee_rates_by_event_origin=non_fee_rates_by_event_origin,
            rate_resolver=rate_resolver,
        )

        for projected in projected_events:
            event = projected.ledger_event
            try:
                prices = rates_by_event_origin[event.event_origin]
                match_event_fifo(
                    projected.projected_event,
                    prices=prices,
                    event_origin=event.event_origin,
                    timestamp=event.timestamp,
                    open_lots_by_asset=self._open_lots_by_asset,
                    acquisitions=self._acquisitions,
                    disposals=self._disposals,
                )
            except AcquisitionDisposalProjectionError as error:
                _add_event_context(error=error, event=event)
                raise

        return self.projection()


def _value_standard_non_fee_events(
    *,
    projected_events: Sequence[_ProjectedLedgerEvent],
    rate_resolver: _DirectRateResolver,
) -> _StandardNonFeeValuation:
    raise NotImplementedError


def _index_anchors(
    *,
    projected_events: Sequence[_ProjectedLedgerEvent],
    rates_by_event_origin: Mapping[EventOrigin, Mapping[AssetId, Decimal]],
) -> dict[AssetId, list[_Anchor]]:
    raise NotImplementedError


def _resolve_non_fee_events_by_anchor(
    *,
    unresolved_events: Sequence[_ProjectedLedgerEvent],
    anchors: Mapping[AssetId, Sequence[_Anchor]],
    rate_resolver: _DirectRateResolver,
) -> dict[EventOrigin, dict[AssetId, Decimal]]:
    raise NotImplementedError


def _complete_rates_with_fees(
    *,
    projected_events: Sequence[_ProjectedLedgerEvent],
    non_fee_rates_by_event_origin: Mapping[EventOrigin, Mapping[AssetId, Decimal]],
    rate_resolver: _DirectRateResolver,
) -> dict[EventOrigin, dict[AssetId, Decimal]]:
    raise NotImplementedError


def _add_event_context(
    *,
    error: AcquisitionDisposalProjectionError,
    event: LedgerEvent,
) -> None:
    error.args = (f"{error} event_origin={event.event_origin} @{event.timestamp.isoformat()}",)
    error.event = event
