from collections import defaultdict, deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from ..ledger import AssetId, EventOrigin, LedgerEvent
from ..pricing import PriceProvider
from .errors import AcquisitionDisposalProjectionError, AcquisitionDisposalUnresolvedRatesError
from .fifo import match_event_fifo
from .models import AcquisitionLot, DisposalLink
from .pipeline_types import _LotBalance, _ProjectedEvent
from .quantities import project_event_quantities
from .valuation import _DirectRateResolver, _value_fee_groups, _value_non_fee_groups


@dataclass(frozen=True)
class AcquisitionDisposalProjection:
    acquisition_lots: list[AcquisitionLot]
    disposal_links: list[DisposalLink]


@dataclass(frozen=True)
class _ProjectedLedgerEvent:
    ledger_event: LedgerEvent
    projected_event: _ProjectedEvent


@dataclass(frozen=True)
class _UnresolvedNonFeeEvent:
    projected: _ProjectedLedgerEvent
    asset_ids: frozenset[AssetId]


@dataclass(frozen=True)
class _StandardNonFeeValuation:
    resolved: dict[EventOrigin, dict[AssetId, Decimal]]
    unresolved: list[_UnresolvedNonFeeEvent]


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
        overrides_by_event_origin: Mapping[EventOrigin, Mapping[AssetId, Decimal]],
    ) -> None:
        self._rate_resolver = _DirectRateResolver(
            price_provider=price_provider,
            overrides_by_event_origin=overrides_by_event_origin,
        )
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
    ) -> AcquisitionDisposalProjection:
        """Events must be provided in chronological order."""
        projected_events = [
            _ProjectedLedgerEvent(
                ledger_event=event,
                projected_event=project_event_quantities(event),
            )
            for event in events
        ]
        standard_valuation = _value_standard_non_fee_events(
            projected_events=projected_events,
            rate_resolver=self._rate_resolver,
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
                    rate_resolver=self._rate_resolver,
                )
            )

        rates_by_event_origin = _complete_rates_with_fees(
            projected_events=projected_events,
            non_fee_rates_by_event_origin=non_fee_rates_by_event_origin,
            rate_resolver=self._rate_resolver,
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
    resolved: dict[EventOrigin, dict[AssetId, Decimal]] = {}
    unresolved: list[_UnresolvedNonFeeEvent] = []

    for projected in projected_events:
        event = projected.ledger_event
        try:
            resolved[event.event_origin] = _value_non_fee_groups(
                projected.projected_event,
                event_origin=event.event_origin,
                timestamp=event.timestamp,
                rate_resolver=rate_resolver,
                borrowed_rates={},
            )
        except AcquisitionDisposalUnresolvedRatesError as error:
            unresolved.append(
                _UnresolvedNonFeeEvent(
                    projected=projected,
                    asset_ids=error.asset_ids,
                )
            )
        except AcquisitionDisposalProjectionError as error:
            _add_event_context(error=error, event=event)
            raise

    return _StandardNonFeeValuation(
        resolved=resolved,
        unresolved=unresolved,
    )


def _index_anchors(
    *,
    projected_events: Sequence[_ProjectedLedgerEvent],
    rates_by_event_origin: Mapping[EventOrigin, Mapping[AssetId, Decimal]],
) -> dict[AssetId, list[_Anchor]]:
    anchors: dict[AssetId, list[_Anchor]] = defaultdict(list)

    for projected in projected_events:
        rates = rates_by_event_origin.get(projected.ledger_event.event_origin)
        if rates is None:
            continue

        for group in projected.projected_event.non_fee_groups:
            rate = rates[group.asset_id]
            # A liability's negative rate must not be lent to another event as an adjacent anchor.
            if rate < 0:
                continue
            anchors[group.asset_id].append(
                _Anchor(
                    event_origin=projected.ledger_event.event_origin,
                    timestamp=projected.ledger_event.timestamp,
                    rate=rate,
                )
            )

    return dict(anchors)


def _resolve_non_fee_events_by_anchor(
    *,
    unresolved_events: Sequence[_UnresolvedNonFeeEvent],
    anchors: Mapping[AssetId, Sequence[_Anchor]],
    rate_resolver: _DirectRateResolver,
) -> dict[EventOrigin, dict[AssetId, Decimal]]:
    resolved: dict[EventOrigin, dict[AssetId, Decimal]] = {}

    for unresolved in unresolved_events:
        event = unresolved.projected.ledger_event
        unresolved_asset_ids = unresolved.asset_ids
        borrowed_rates: dict[AssetId, Decimal] = {}

        while True:
            candidate = min(
                (
                    (asset_id, anchor)
                    for asset_id in unresolved_asset_ids
                    for anchor in anchors.get(asset_id, ())
                    if anchor.event_origin != event.event_origin
                ),
                key=lambda candidate: (
                    abs(candidate[1].timestamp - event.timestamp),
                    candidate[1].event_origin.location.value,
                    candidate[1].event_origin.external_id,
                    candidate[0],
                ),
                default=None,
            )
            if candidate is None:
                if len(unresolved_asset_ids) == 1:
                    unresolved_assets = f"asset={next(iter(unresolved_asset_ids))}"
                else:
                    unresolved_assets = f"assets={','.join(sorted(unresolved_asset_ids))}"
                error = AcquisitionDisposalUnresolvedRatesError(
                    "No standard-valued adjacent anchor is available for unresolved non-fee assets: "
                    f"{unresolved_assets}.",
                    asset_ids=unresolved_asset_ids,
                )
                _add_event_context(error=error, event=event)
                raise error

            asset_id, anchor = candidate
            borrowed_rates[asset_id] = anchor.rate

            try:
                resolved[event.event_origin] = _value_non_fee_groups(
                    unresolved.projected.projected_event,
                    event_origin=event.event_origin,
                    timestamp=event.timestamp,
                    rate_resolver=rate_resolver,
                    borrowed_rates=borrowed_rates,
                )
            except AcquisitionDisposalUnresolvedRatesError as error:
                unresolved_asset_ids = error.asset_ids
                continue
            except AcquisitionDisposalProjectionError as error:
                _add_event_context(error=error, event=event)
                raise
            break

    return resolved


def _complete_rates_with_fees(
    *,
    projected_events: Sequence[_ProjectedLedgerEvent],
    non_fee_rates_by_event_origin: Mapping[EventOrigin, Mapping[AssetId, Decimal]],
    rate_resolver: _DirectRateResolver,
) -> dict[EventOrigin, dict[AssetId, Decimal]]:
    completed: dict[EventOrigin, dict[AssetId, Decimal]] = {}

    for projected in projected_events:
        event = projected.ledger_event
        non_fee_rates = non_fee_rates_by_event_origin[event.event_origin]
        try:
            fee_rates = _value_fee_groups(
                projected.projected_event.fee_groups,
                non_fee_prices=non_fee_rates,
                event_origin=event.event_origin,
                timestamp=event.timestamp,
                rate_resolver=rate_resolver,
            )
        except AcquisitionDisposalProjectionError as error:
            _add_event_context(error=error, event=event)
            raise
        completed[event.event_origin] = dict(non_fee_rates) | fee_rates

    return completed


def _add_event_context(
    *,
    error: AcquisitionDisposalProjectionError,
    event: LedgerEvent,
) -> None:
    error.args = (f"{error} event_origin={event.event_origin} @{event.timestamp.isoformat()}",)
    error.event = event
