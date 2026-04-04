from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Iterable, cast

from domain.acquisition_disposal import AcquisitionLot, DisposalLink
from domain.acquisition_disposal_projection import AcquisitionDisposalProjection
from domain.ledger import DisposalId, LedgerEvent, LotId
from domain.tax_event import TaxEvent, TaxEventKind

from .formatting import format_currency


def generate_tax_events(
    projection: AcquisitionDisposalProjection, events: Iterable[LedgerEvent], *, tax_free_days: int = 365
) -> list[TaxEvent]:
    """Create taxable events from disposals and reward acquisitions."""
    lots_by_id: dict[LotId, AcquisitionLot] = {lot.id: lot for lot in projection.acquisition_lots}
    tax_free_threshold = timedelta(days=tax_free_days)
    tax_events: list[TaxEvent] = []
    _ = events

    for link in projection.disposal_links:
        lot = lots_by_id[link.lot_id]

        if (link.timestamp - lot.timestamp) >= tax_free_threshold:
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
    projection: AcquisitionDisposalProjection,
    events: Iterable[LedgerEvent],
) -> list[WeeklyTaxSummary]:
    """Aggregate taxable events per ISO week, recomputing valuations from the acquisition/disposal projection."""
    weekly_totals: dict[date, tuple[int, Decimal, Decimal, Decimal]] = {}

    lots_by_id: dict[LotId, AcquisitionLot] = {lot.id: lot for lot in projection.acquisition_lots}
    links_by_id: dict[DisposalId, DisposalLink] = {link.id: link for link in projection.disposal_links}
    _ = events

    for tax_event in tax_events:
        proceeds: Decimal
        cost_basis: Decimal
        gain: Decimal
        timestamp: datetime

        if tax_event.kind == TaxEventKind.DISPOSAL:
            link_id = cast(DisposalId, tax_event.source_id)
            link = links_by_id[link_id]
            lot = lots_by_id[link.lot_id]

            proceeds = link.proceeds_total
            cost_basis = link.quantity_used * lot.cost_per_unit
            gain = proceeds - cost_basis
            timestamp = link.timestamp
        elif tax_event.kind == TaxEventKind.REWARD:
            lot_id = cast(LotId, tax_event.source_id)
            lot = lots_by_id[lot_id]

            proceeds = lot.quantity_acquired * lot.cost_per_unit
            cost_basis = Decimal(0)
            gain = proceeds
            timestamp = lot.timestamp
        else:
            raise ValueError(f"Unexpected tax event kind: {tax_event.kind}")

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
