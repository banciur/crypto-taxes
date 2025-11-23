from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from domain.inventory import InventoryResult
from domain.ledger import AcquisitionLot, LedgerEvent

from .formatting import format_currency


@dataclass
class TaxEvent:
    disposal_link_id: UUID
    taxable_gain: Decimal


def generate_tax_events(
    inventory_result: InventoryResult, events: Iterable[LedgerEvent], *, tax_free_days: int = 365
) -> list[TaxEvent]:
    """Create per-disposal tax events, skipping links that are past the tax-free window."""
    events_by_id = {event.id: event for event in events}
    legs_to_event: dict[UUID, LedgerEvent] = {}
    for event in events_by_id.values():
        for leg in event.legs:
            legs_to_event[leg.id] = event

    lots_by_id: dict[UUID, AcquisitionLot] = {lot.id: lot for lot in inventory_result.acquisition_lots}
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

        acquisition_event = events_by_id.get(lot.acquired_event_id)
        if acquisition_event is None:
            msg = f"Unknown acquisition event {lot.acquired_event_id} for lot {lot.id}"
            raise ValueError(msg)

        if (disposal_event.timestamp - acquisition_event.timestamp) >= tax_free_threshold:
            continue

        cost_basis = link.quantity_used * lot.cost_eur_per_unit
        gain = link.proceeds_total_eur - cost_basis
        tax_events.append(TaxEvent(disposal_link_id=link.id, taxable_gain=gain))

    return tax_events


@dataclass
class WeeklyTaxSummary:
    week_start: date
    week_end: date
    taxable_disposals: int
    proceeds: Decimal
    cost_basis: Decimal
    taxable_gain: Decimal


def compute_weekly_tax_summary(
    tax_events: Iterable[TaxEvent],
    inventory_result: InventoryResult,
    events: Iterable[LedgerEvent],
) -> list[WeeklyTaxSummary]:
    """Aggregate taxable disposals per ISO week, skipping weeks with no events."""
    weekly_totals: dict[date, tuple[int, Decimal, Decimal, Decimal]] = {}
    lots_by_id: dict[UUID, AcquisitionLot] = {lot.id: lot for lot in inventory_result.acquisition_lots}
    links_by_id = {link.id: link for link in inventory_result.disposal_links}
    legs_to_event: dict[UUID, LedgerEvent] = {}
    for event in events:
        for leg in event.legs:
            legs_to_event[leg.id] = event

    for tax_event in tax_events:
        link = links_by_id.get(tax_event.disposal_link_id)
        if link is None:
            msg = f"Unknown disposal link {tax_event.disposal_link_id}"
            raise ValueError(msg)

        disposal_event = legs_to_event.get(link.disposal_leg_id)
        if disposal_event is None:
            msg = f"Unknown disposal leg {link.disposal_leg_id}"
            raise ValueError(msg)

        lot = lots_by_id.get(link.lot_id)
        if lot is None:
            msg = f"Unknown lot {link.lot_id} for disposal {link.id}"
            raise ValueError(msg)

        week_start = disposal_event.timestamp.date() - timedelta(days=disposal_event.timestamp.weekday())
        proceeds_eur = link.proceeds_total_eur
        cost_basis_eur = link.quantity_used * lot.cost_eur_per_unit
        gain_eur = tax_event.taxable_gain

        totals = weekly_totals.get(week_start, (0, Decimal("0"), Decimal("0"), Decimal("0")))
        disposals, proceeds, costs, gains = totals
        weekly_totals[week_start] = (
            disposals + 1,
            proceeds + proceeds_eur,
            costs + cost_basis_eur,
            gains + gain_eur,
        )

    summaries: list[WeeklyTaxSummary] = []
    for week_start, (disposals, proceeds, costs, gains) in sorted(weekly_totals.items()):
        if disposals == 0:
            continue
        summaries.append(
            WeeklyTaxSummary(
                week_start=week_start,
                week_end=week_start + timedelta(days=6),
                taxable_disposals=disposals,
                proceeds=proceeds,
                cost_basis=costs,
                taxable_gain=gains,
            )
        )

    return summaries


def render_weekly_tax_summary(weeks: Iterable[WeeklyTaxSummary]) -> None:
    weeks_list = list(weeks)
    print("Weekly taxable gains (EUR):")
    if not weeks_list:
        print("  (no taxable disposals)")
        return

    week_label_width = max(
        len("Week"), max((len(f"{row.week_start} → {row.week_end}") for row in weeks_list), default=0)
    )
    count_width = max(len("Disposals"), max((len(str(row.taxable_disposals)) for row in weeks_list), default=0))
    proceeds_width = max(len("Proceeds"), max((len(format_currency(row.proceeds)) for row in weeks_list), default=0))
    cost_width = max(len("Cost basis"), max((len(format_currency(row.cost_basis)) for row in weeks_list), default=0))
    gain_width = max(
        len("Taxable gain"), max((len(format_currency(row.taxable_gain)) for row in weeks_list), default=0)
    )

    header = (
        f"{'Week':<{week_label_width}} "
        f"{'Disposals':>{count_width}} "
        f"{'Proceeds':>{proceeds_width}} "
        f"{'Cost basis':>{cost_width}} "
        f"{'Taxable gain':>{gain_width}}"
    )
    lines = [header, "-" * len(header)]

    for row in weeks_list:
        week_label = f"{row.week_start} → {row.week_end}"
        lines.append(
            f"{week_label:<{week_label_width}} "
            f"{row.taxable_disposals:>{count_width}} "
            f"{format_currency(row.proceeds):>{proceeds_width}} "
            f"{format_currency(row.cost_basis):>{cost_width}} "
            f"{format_currency(row.taxable_gain):>{gain_width}}"
        )

    print("\n".join(lines))
