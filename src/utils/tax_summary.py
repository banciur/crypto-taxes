from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Iterable, cast

from domain.inventory import InventoryResult
from domain.ledger import AcquisitionLot, DisposalId, DisposalLink, EventType, LedgerEvent, LedgerLeg, LegId, LotId

from .formatting import format_currency


class TaxEventKind(StrEnum):
    DISPOSAL = "DISPOSAL"
    REWARD = "REWARD"


@dataclass
class TaxEvent:
    source_id: DisposalId | LotId
    kind: TaxEventKind
    taxable_gain: Decimal


def generate_tax_events(
    inventory_result: InventoryResult, events: Iterable[LedgerEvent], *, tax_free_days: int = 365
) -> list[TaxEvent]:
    """Create taxable events from disposals and reward acquisitions."""
    legs_by_id: dict[LegId, LedgerLeg] = {}
    legs_to_event: dict[LegId, LedgerEvent] = {}
    for event in events:
        for leg in event.legs:
            legs_to_event[leg.id] = event
            legs_by_id[leg.id] = leg

    lots_by_id: dict[LotId, AcquisitionLot] = {lot.id: lot for lot in inventory_result.acquisition_lots}
    tax_free_threshold = timedelta(days=tax_free_days)
    tax_events: list[TaxEvent] = []

    for link in inventory_result.disposal_links:
        disposal_event = legs_to_event.get(link.disposal_leg_id)
        if disposal_event is None:
            msg = f"Unknown disposal leg {link.disposal_leg_id}"
            raise ValueError(msg)

        lot = lots_by_id.get(link.lot_id)
        if lot is None:
            msg = f"Unknown lot {link.lot_id} for disposal {link.disposal_leg_id}"
            raise ValueError(msg)

        acquisition_event = legs_to_event.get(lot.acquired_leg_id)
        if acquisition_event is None:
            msg = f"Unknown acquisition event for leg {lot.acquired_leg_id}"
            raise ValueError(msg)

        if (disposal_event.timestamp - acquisition_event.timestamp) >= tax_free_threshold:
            continue

        cost_basis = link.quantity_used * lot.cost_per_unit
        proceeds = link.proceeds_total
        gain = proceeds - cost_basis
        tax_events.append(
            TaxEvent(
                source_id=link.id,
                kind=TaxEventKind.DISPOSAL,
                taxable_gain=gain,
            )
        )

    for lot in inventory_result.acquisition_lots:
        acquisition_leg = legs_by_id.get(lot.acquired_leg_id)
        if acquisition_leg is None:
            msg = f"Unknown acquisition leg {lot.acquired_leg_id} for lot {lot.id}"
            raise ValueError(msg)

        acquisition_event = legs_to_event.get(lot.acquired_leg_id)
        if acquisition_event is None:
            msg = f"Unknown acquisition event for leg {lot.acquired_leg_id}"
            raise ValueError(msg)

        if acquisition_event.event_type != EventType.REWARD:
            continue

        proceeds = acquisition_leg.quantity * lot.cost_per_unit
        tax_events.append(
            TaxEvent(
                source_id=lot.id,
                kind=TaxEventKind.REWARD,
                taxable_gain=proceeds,
            )
        )

    return tax_events


@dataclass
class WeeklyTaxSummary:
    week_start: date
    week_end: date
    taxable_events: int
    proceeds: Decimal
    cost_basis: Decimal
    taxable_gain: Decimal


def compute_weekly_tax_summary(
    tax_events: Iterable[TaxEvent],
    inventory_result: InventoryResult,
    events: Iterable[LedgerEvent],
) -> list[WeeklyTaxSummary]:
    """Aggregate taxable events per ISO week, recomputing valuations from inventory and events."""
    weekly_totals: dict[date, tuple[int, Decimal, Decimal, Decimal]] = {}
    lots_by_id: dict[LotId, AcquisitionLot] = {lot.id: lot for lot in inventory_result.acquisition_lots}
    links_by_id: dict[DisposalId, DisposalLink] = {link.id: link for link in inventory_result.disposal_links}
    legs_by_id: dict[LegId, LedgerLeg] = {}
    leg_to_event: dict[LegId, LedgerEvent] = {}
    for event in events:
        for leg in event.legs:
            legs_by_id[leg.id] = leg
            leg_to_event[leg.id] = event

    for tax_event in tax_events:
        proceeds: Decimal
        cost_basis: Decimal
        gain: Decimal
        timestamp: datetime

        if tax_event.kind == TaxEventKind.DISPOSAL:
            link_id = cast(DisposalId, tax_event.source_id)
            link = links_by_id.get(link_id)
            if link is None:
                msg = f"Unknown disposal link {tax_event.source_id}"
                raise ValueError(msg)

            lot = lots_by_id.get(link.lot_id)
            if lot is None:
                msg = f"Unknown lot {link.lot_id} for disposal {link.id}"
                raise ValueError(msg)

            disposal_event = leg_to_event.get(link.disposal_leg_id)
            if disposal_event is None:
                msg = f"Unknown disposal leg {link.disposal_leg_id}"
                raise ValueError(msg)

            proceeds = link.proceeds_total
            cost_basis = link.quantity_used * lot.cost_per_unit
            gain = proceeds - cost_basis
            timestamp = disposal_event.timestamp
        elif tax_event.kind == TaxEventKind.REWARD:
            lot_id = cast(LotId, tax_event.source_id)
            lot = lots_by_id.get(lot_id)
            if lot is None:
                msg = f"Unknown reward lot {tax_event.source_id}"
                raise ValueError(msg)

            acquisition_leg = legs_by_id.get(lot.acquired_leg_id)
            if acquisition_leg is None:
                msg = f"Unknown acquisition leg {lot.acquired_leg_id} for lot {lot.id}"
                raise ValueError(msg)

            acquisition_event = leg_to_event.get(lot.acquired_leg_id)
            if acquisition_event is None:
                msg = f"Unknown acquisition event for leg {lot.acquired_leg_id}"
                raise ValueError(msg)
            if acquisition_event.event_type != EventType.REWARD:
                msg = f"Lot {lot.id} not linked to REWARD event {acquisition_event.id}"
                raise ValueError(msg)

            proceeds = acquisition_leg.quantity * lot.cost_per_unit
            cost_basis = Decimal("0")
            gain = proceeds
            timestamp = acquisition_event.timestamp

        week_start = timestamp.date() - timedelta(days=timestamp.weekday())

        totals = weekly_totals.get(week_start, (0, Decimal("0"), Decimal("0"), Decimal("0")))
        count, proceeds_total, costs_total, gains_total = totals
        weekly_totals[week_start] = (
            count + 1,
            proceeds_total + proceeds,
            costs_total + cost_basis,
            gains_total + gain,
        )

    summaries: list[WeeklyTaxSummary] = []
    for week_start, (count, proceeds, costs, gains) in sorted(weekly_totals.items()):
        if count == 0:
            continue
        summaries.append(
            WeeklyTaxSummary(
                week_start=week_start,
                week_end=week_start + timedelta(days=6),
                taxable_events=count,
                proceeds=proceeds,
                cost_basis=costs,
                taxable_gain=gains,
            )
        )

    return summaries


def render_weekly_tax_summary(weeks: Iterable[WeeklyTaxSummary]) -> None:
    weeks_list = list(weeks)
    print("Weekly taxable totals (EUR):")
    if not weeks_list:
        print("  (no taxable events)")
        return

    week_label_width = max(
        len("Week"), max((len(f"{row.week_start} → {row.week_end}") for row in weeks_list), default=0)
    )
    count_width = max(len("Events"), max((len(str(row.taxable_events)) for row in weeks_list), default=0))
    proceeds_width = max(len("Proceeds"), max((len(format_currency(row.proceeds)) for row in weeks_list), default=0))
    cost_width = max(len("Cost basis"), max((len(format_currency(row.cost_basis)) for row in weeks_list), default=0))
    gain_width = max(
        len("Taxable gain"), max((len(format_currency(row.taxable_gain)) for row in weeks_list), default=0)
    )

    header = (
        f"{'Week':<{week_label_width}} "
        f"{'Events':>{count_width}} "
        f"{'Proceeds':>{proceeds_width}} "
        f"{'Cost basis':>{cost_width}} "
        f"{'Taxable gain':>{gain_width}}"
    )
    lines = [header, "-" * len(header)]

    for row in weeks_list:
        week_label = f"{row.week_start} → {row.week_end}"
        lines.append(
            f"{week_label:<{week_label_width}} "
            f"{row.taxable_events:>{count_width}} "
            f"{format_currency(row.proceeds):>{proceeds_width}} "
            f"{format_currency(row.cost_basis):>{cost_width}} "
            f"{format_currency(row.taxable_gain):>{gain_width}}"
        )

    print("\n".join(lines))
